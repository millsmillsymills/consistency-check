"""Lightweight git introspection helpers for rule checks."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def tracked_files(repo_path: Path) -> frozenset[str] | None:
    """Return the repo-relative paths git considers tracked, or None if it cannot be asked.

    ``None`` and an empty set are different answers and callers must not
    conflate them: an empty set says "git says nothing is tracked", and every
    caller that treats the two alike grades the whole working tree, reporting
    paths the repo never committed.

    ``core.fsmonitor`` is disabled explicitly because git runs it as the
    auditing user, and the audit points this at repos it did not clone.
    """
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=",
                "--no-optional-locks",
                "-C",
                str(repo_path),
                "ls-files",
            ],
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
