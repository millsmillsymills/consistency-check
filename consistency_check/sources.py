"""Source-file discovery shared by rule modules.

Pure and side-effect-free: every function reads repo files and returns data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo


def python_sources(repo: Repo) -> list[Path]:
    """Every .py file under the repo's src/ directory."""
    src = repo.path / "src"
    return list(src.rglob("*.py")) if src.is_dir() else []


def go_sources(repo: Repo) -> list[Path]:
    """Every non-test .go file in the repo.

    Skips dot-prefix dirs (.git, .worktrees, .venv, etc.) so stale copies
    under git worktrees or vendor caches don't poison the heuristics.
    """
    return [
        p
        for p in repo.path.rglob("*.go")
        if not any(part.startswith(".") for part in p.parts) and not p.name.endswith("_test.go")
    ]


def combined_source_text(repo: Repo) -> str:
    """Concatenated text of the repo's language-appropriate source files."""
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
