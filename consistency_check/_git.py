"""Lightweight git introspection helpers for rule checks."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def tracked_files(repo_path: Path) -> frozenset[str]:
    """Return the set of repo-relative paths git considers tracked.

    Empty set if `repo_path` is not a git repo or `git ls-files` errors.
    """
    if not (repo_path / ".git").exists():
        return frozenset()
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if result.returncode != 0:
        return frozenset()
    return frozenset(line for line in result.stdout.splitlines() if line)
