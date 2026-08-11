"""Source-file discovery shared by rule modules.

Pure and side-effect-free: every function reads repo files and returns data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from consistency_check.types import Repo


def python_sources(repo: Repo) -> list[Path]:
    """Every .py file under the repo's src/ directory."""
    src = repo.path / "src"
    return list(src.rglob("*.py")) if src.is_dir() else []


_GO_EXCLUDED_DIRS = frozenset({"vendor", "third_party", "testdata"})


def go_sources(repo: Repo) -> list[Path]:
    """Every non-test .go file the repo itself owns.

    Skips dot-prefix dirs (.git, .worktrees, .venv, etc.) so stale copies
    under git worktrees or vendor caches don't poison the heuristics, and skips
    vendored/third-party trees so a dependency's source is not graded as if the
    repo had written it.

    Exclusions are tested against the repo-relative path only. Matching against
    ``p.parts`` would test every ancestor too, so a checkout that merely *sits*
    under a directory named ``vendor`` or ``.worktrees`` would yield no sources
    at all and pass every Go rule on an empty list.
    """
    return [
        p
        for p in repo.path.rglob("*.go")
        if not any(
            part.startswith(".") or part in _GO_EXCLUDED_DIRS
            for part in p.relative_to(repo.path).parts
        )
        and not p.name.endswith("_test.go")
    ]


def combined_source_text(repo: Repo) -> str:
    """Concatenated text of the repo's language-appropriate source files."""
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)


def _consume_quoted(text: str, i: int) -> int:
    """Index just past the string literal opening at ``i``.

    Only a backtick raw string may span lines. Ending the others at the newline
    keeps one unbalanced quote from consuming the rest of the file.

    An opener with no closer yields the index just past the opener itself, not
    the end of the text: see ``_unclosed`` for why swallowing the remainder is
    the one outcome a scanner feeding an auditor must not have.
    """
    quote = text[i]
    start = i
    i += 1
    while i < len(text):
        if text[i] == "\n" and quote != "`":
            return i
        if text[i] == "\\" and quote != "`":
            # An escape must not step over the newline that ends the literal, or
            # the scan runs on into the next line and grades that line's string
            # contents as code.
            if text[i + 1 : i + 2] == "\n":
                return i + 1
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return _unclosed(start, 1)


def _unclosed(start: int, delim_len: int) -> int:
    """Where to resume after a literal opener that is never closed.

    Consuming to end of input is what the language does, but it is the wrong
    thing for an auditor: everything after the opener is blanked, so the rules
    read a file with no stdout writes, no untimed clients and no retired error
    codes, and the repo passes. Treating the stray delimiter as an ordinary
    character instead keeps the rest of the file readable. The cost is that an
    unterminated literal's prose is graded as code, which can only produce a
    false failure — the direction an audit is allowed to be wrong in.
    """
    return start + delim_len


def mask_literal_contents(text: str) -> str:
    """Replace the interior of every string literal with underscores.

    Keeps the literal's shape — so a construction like ``Server("x")`` still
    reads as a call with an argument — while making the *contents* unreadable to
    the call-shaped patterns, which would otherwise match a constructor named
    inside an error message.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in "\"'`":
            end = _consume_quoted(text, i)
            span = text[i:end]
            closed = len(span) >= 2 and span[-1] == span[0]
            body = span[1:-1] if closed else span[1:]
            out.append(span[0] + re.sub(r"[^\n]", "_", body) + (span[0] if closed else ""))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def mask_literal_braces(text: str) -> str:
    """Blank brace characters inside string literals, keeping offsets stable.

    Balanced-brace scanning over text that deliberately keeps its literals would
    otherwise end a composite literal early at a ``}`` written inside a
    description string.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in "\"'`":
            end = _consume_quoted(text, i)
            out.append(re.sub(r"[{}]", " ", text[i:end]))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def strip_go_comments(text: str) -> str:
    """Remove Go ``//`` and ``/* */`` comments, keeping literals and line count intact.

    Quote-aware, and one pass over the whole text rather than one per line. A
    backtick raw string spans lines, so a per-line strip cannot tell that a
    ``//`` sits inside one; truncating the line that closes the string hands the
    literal scanner an unterminated raw string, which then consumes every
    remaining line. Both comment forms are recognised here so that neither can
    be opened from inside a literal nor a literal from inside a comment.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end == -1 else end
        elif text[i] in "\"'`":
            end = _consume_quoted(text, i)
            out.append(text[i:end])
            i = end
        elif text.startswith("/*", i):
            end = len(text) if (close := text.find("*/", i + 2)) == -1 else close + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _consume_python_quoted(text: str, i: int) -> int:
    r"""Index just past the Python string literal opening at ``i``.

    Only a triple-quoted string may span lines. Ending the others at the newline
    keeps one unbalanced quote from consuming the rest of the file. A backslash
    escapes the following character in raw strings too — ``r"\"`` is not a
    terminated literal — so the escape branch is unconditional.
    """
    delim = text[i] * 3 if text.startswith(text[i] * 3, i) else text[i]
    start = i
    i += len(delim)
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "\n" and len(delim) == 1:
            return i
        if text.startswith(delim, i):
            return i + len(delim)
        i += 1
    return _unclosed(start, len(delim))


def strip_python_comments(text: str) -> str:
    """Remove ``#`` comments in one quote-aware pass, keeping literals intact.

    One pass over the whole text rather than one per line, for the reason
    ``strip_go_comments`` gives: a triple-quoted string spans lines, so a
    per-line strip cannot tell that a ``#`` sits inside one. Truncating the line
    that closes the string orphans the opening quotes, which then pair with the
    next triple-quoted string in the file and delete everything between.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "#":
            end = text.find("\n", i)
            i = len(text) if end == -1 else end
        elif text[i] in "\"'":
            end = _consume_python_quoted(text, i)
            out.append(text[i:end])
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def strip_python_literals(text: str) -> str:
    """Drop every Python string literal, keeping the line count."""
    return _drop_python_literals(text, triple_only=False)


def strip_python_docstrings(text: str) -> str:
    """Drop triple-quoted strings only, keeping other literals and the line count.

    For callers that need the value inside a literal — a ``transport="http"``
    argument — but not the prose inside a docstring.
    """
    return _drop_python_literals(text, triple_only=True)


def _drop_python_literals(text: str, *, triple_only: bool) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in "\"'":
            end = _consume_python_quoted(text, i)
            span = text[i:end]
            keep = triple_only and not span.startswith(('"""', "'''"))
            out.append(span if keep else "\n" * text.count("\n", i, end))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def strip_go_literals(text: str) -> str:
    """Drop every Go string, rune, and raw-string body, keeping the line count.

    Go has three quote forms and a scanner that knows only two misreads both
    ways: a backtick raw string's contents are graded as code, and an apostrophe
    inside one opens a rune span that deletes every line up to the next
    apostrophe. Only a raw string may span lines; the other two end at the
    newline they cannot cross.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] in "\"'`":
            end = _consume_quoted(text, i)
            out.append("\n" * text.count("\n", i, end))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def code_only(text: str, line_comment: str) -> str:
    """Strip comments then string literals, so prose cannot register as code.

    Every comment goes first because the literal scan is comment-blind: an
    apostrophe or a lone ``"`` written in a comment pairs with the next quote in
    real code, and the span between them — up to the whole rest of the file — is
    deleted before any check reads it. An empty file passes everything.
    """
    if line_comment == "//":
        return strip_go_literals(strip_go_comments(text))
    return strip_python_literals(strip_python_comments(text))


def code_and_literals(text: str, line_comment: str) -> str:
    """Strip docstrings and comments but keep string literals.

    ``code_only`` drops literals too, which is right for call-shaped heuristics
    but wrong when the value being detected *is* a literal, e.g. a
    ``transport="streamable-http"`` argument. Go has no docstring form, so its
    path stops at comments.
    """
    if line_comment == "//":
        return strip_go_comments(text)
    return strip_python_docstrings(strip_python_comments(text))


def _combined(repo: Repo, scrub: Callable[[str, str], str]) -> str:
    """Join the repo's sources, scrubbing each file before the join.

    A span deleted from the concatenation could otherwise start in one file and
    end in another, erasing every file between them.
    """
    marker = "#" if repo.language == "python" else "//"
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    return "\n".join(
        scrub(p.read_text(encoding="utf-8", errors="replace"), marker) for p in sources
    )


def combined_code_only_text(repo: Repo) -> str:
    """``combined_code_text`` with string literals dropped too.

    For checks whose subject is a value written in code, not in a literal: a
    migration note ("do not use -32002") names the thing it forbids, and reading
    it as the thing itself inverts the rule.
    """
    return _combined(repo, code_only)


def combined_code_text(repo: Repo) -> str:
    """``combined_source_text`` with docstrings and comments removed, literals kept."""
    return _combined(repo, code_and_literals)
