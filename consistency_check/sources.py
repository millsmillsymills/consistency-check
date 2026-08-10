"""Source-file discovery shared by rule modules.

Pure and side-effect-free: every function reads repo files and returns data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    """
    return [
        p
        for p in repo.path.rglob("*.go")
        if not any(part.startswith(".") or part in _GO_EXCLUDED_DIRS for part in p.parts)
        and not p.name.endswith("_test.go")
    ]


def combined_source_text(repo: Repo) -> str:
    """Concatenated text of the repo's language-appropriate source files."""
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)


def code_only(text: str, line_comment: str) -> str:
    """Strip string literals then line comments, so prose cannot register as code."""
    text = STRING_LITERAL.sub("", text)
    return re.sub(rf"{re.escape(line_comment)}.*", "", text)


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
    """
    text = _BLOCK_STRING.sub("", text)
    return "\n".join(_strip_line_comment(line, line_comment) for line in text.splitlines())


def combined_code_text(repo: Repo) -> str:
    """``combined_source_text`` with docstrings and comments removed, literals kept."""
    return code_and_literals(combined_source_text(repo), "#" if repo.language == "python" else "//")
