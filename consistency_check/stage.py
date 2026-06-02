"""Maturity-stage parsing, SCOPE.md parsing, and drift signals.

Pure and side-effect-free: every function reads repo files and returns data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Stage

if TYPE_CHECKING:
    from consistency_check.types import Repo

_STAGE_ORDER = (Stage.S0, Stage.S1, Stage.S2, Stage.S3, Stage.S4)
_STATUS_SECTION = re.compile(r"(?ims)^##\s+status\b(.*?)(?=^##\s|\Z)")
_STAGE_TOKEN = re.compile(r"\bS([0-4])\b")
_SURFACE_SECTION = re.compile(r"(?ims)^##\s+surface\b(.*?)(?=^##\s|\Z)")
_EXCEPTION_HEADING = re.compile(r"(?im)^##\s+scope exception\b")


def stage_rank(stage: Stage) -> int:
    """Return the 0-based ordinal of ``stage`` (S0 -> 0 ... S4 -> 4)."""
    return _STAGE_ORDER.index(stage)


def next_stage(stage: Stage) -> Stage | None:
    """Return the stage one rung above ``stage``, or None at the top (S4)."""
    idx = _STAGE_ORDER.index(stage)
    return _STAGE_ORDER[idx + 1] if idx + 1 < len(_STAGE_ORDER) else None


def declared_stage(repo: Repo) -> Stage | None:
    """Read the repo's declared stage from the README ``## Status`` section.

    Returns the parsed Stage, or None when the README is missing, has no
    ``## Status`` section, or that section carries no S0-S4 token (unstaged).
    """
    readme = repo.path / "README.md"
    if not readme.is_file():
        return None
    section = _STATUS_SECTION.search(readme.read_text(encoding="utf-8", errors="replace"))
    if section is None:
        return None
    token = _STAGE_TOKEN.search(section.group(1))
    if token is None:
        return None
    return Stage(f"S{token.group(1)}")


def surface_operations(repo: Repo) -> list[str]:
    """Return the declared operations from SCOPE.md ``## Surface`` (one per bullet)."""
    scope = repo.path / "SCOPE.md"
    if not scope.is_file():
        return []
    section = _SURFACE_SECTION.search(scope.read_text(encoding="utf-8", errors="replace"))
    if section is None:
        return []
    ops: list[str] = []
    for line in section.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            ops.append(stripped[1:].strip())
    return ops


def has_scope_exception(repo: Repo) -> bool:
    """Return True when SCOPE.md declares a ``## Scope exception`` heading."""
    scope = repo.path / "SCOPE.md"
    if not scope.is_file():
        return False
    text = scope.read_text(encoding="utf-8", errors="replace")
    return _EXCEPTION_HEADING.search(text) is not None
