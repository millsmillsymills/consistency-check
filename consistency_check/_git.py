"""Lightweight git introspection helpers for rule checks."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def tracked_files(repo_path: Path) -> frozenset[str] | None:
    """Return the repo-relative paths git considers tracked, or None if it cannot be asked.

    ``None`` and an empty set are different answers and callers must not
    conflate them. Returning an empty set for "git is unavailable" made the
    idiom ``if tracked and rel not in tracked`` fall through, so rules that
    exist to grade *tracked* content silently graded the whole working tree —
    and reported untracked files' paths into a public issue.
    """
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return frozenset(line for line in result.stdout.splitlines() if line)
