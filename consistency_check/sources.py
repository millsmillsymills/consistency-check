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

STRING_LITERAL = re.compile(
    r"""
    '''.*?'''               # triple single
    | \"\"\".*?\"\"\"       # triple double
    | "(?:\\.|[^"\\])*"     # double-quoted
    | '(?:\\.|[^'\\])*'     # single-quoted
    """,
    re.VERBOSE | re.DOTALL,
)


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
    """
    quote = text[i]
    i += 1
    while i < len(text):
        if text[i] == "\n" and quote != "`":
            return i
        if text[i] == "\\" and quote != "`":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return i


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


def strip_block_comments(text: str) -> str:
    """Remove Go ``/* */`` comments, keeping string literals and line count intact.

    Quote-aware because callers that keep literals would otherwise see a ``/*``
    inside a URL open a comment that swallows the rest of the file. ``//`` lines
    are copied through untouched for the same reason: a ``/*`` or a lone
    apostrophe written in prose there must not open a span.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = len(text) if end == -1 else end
            out.append(text[i:end])
            i = end
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


def strip_go_literals(text: str) -> str:
    """Drop every Go string, rune, and raw-string body, keeping the line count.

    ``STRING_LITERAL`` is backtick-blind, which broke both ways on Go: a raw
    string's contents were read as code, and an apostrophe inside one opened a
    single-quote span that deleted every line up to the next apostrophe. The
    same scanner the masking helpers use knows all three quote forms and ends an
    interpreted string at the newline it cannot cross.
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
        text = strip_block_comments(text)
    text = "\n".join(_strip_line_comment(line, line_comment) for line in text.splitlines())
    return strip_go_literals(text) if line_comment == "//" else STRING_LITERAL.sub("", text)


_BLOCK_STRING = re.compile(r"'''.*?'''|\"\"\".*?\"\"\"", re.DOTALL)


def _strip_line_comment(line: str, marker: str) -> str:
    """Drop a trailing line comment, ignoring a marker that sits inside a string.

    Keeps `url = "https://example.com"` intact, which matters because callers of
    this function — unlike ``code_only`` — need the string literals preserved.
    """
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif line.startswith(marker, i):
            return line[:i]
        i += 1
    return line


def code_and_literals(text: str, line_comment: str) -> str:
    """Strip docstrings and comments but keep string literals.

    ``code_only`` drops literals too, which is right for call-shaped heuristics
    but wrong when the value being detected *is* a literal, e.g. a
    ``transport="streamable-http"`` argument.

    ``_BLOCK_STRING`` is Python-only. Applied to Go it pairs ``\"\"\"`` sequences
    that occur inside unrelated raw strings and deletes everything between them.
    It also runs last, because two ``#`` comments that merely *mention* ``\"\"\"``
    would otherwise pair and erase the code between them.
    """
    if line_comment == "//":
        text = strip_block_comments(text)
    text = "\n".join(_strip_line_comment(line, line_comment) for line in text.splitlines())
    return _BLOCK_STRING.sub("", text) if line_comment == "#" else text


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
