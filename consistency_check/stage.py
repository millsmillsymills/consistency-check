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


def _has_source_tree(repo: Repo) -> bool:
    if repo.language == "go":
        return (repo.path / "cmd").is_dir() or (repo.path / "internal").is_dir()
    return (repo.path / "src").is_dir()


def _has_ci(repo: Repo) -> bool:
    workflows = repo.path / ".github" / "workflows"
    return workflows.is_dir() and any(
        p.suffix in {".yml", ".yaml"} for p in workflows.iterdir() if p.is_file()
    )


def _has_integration_marker(repo: Repo) -> bool:
    return (repo.path / "tests" / "integration").is_dir() or (repo.path / "integration").is_dir()


def _has_release_path(repo: Repo) -> bool:
    workflows = repo.path / ".github" / "workflows"
    if workflows.is_dir() and any("release" in p.name.lower() for p in workflows.iterdir()):
        return True
    return (repo.path / "mcpb").exists()


def _floor_drift(repo: Repo, declared: Stage, has_src: bool) -> str | None:
    """Floor checks: declared stage implies structure that is absent."""
    if declared is Stage.S0 and has_src:
        return "declared S0 but a source tree exists"
    if stage_rank(declared) >= stage_rank(Stage.S1) and not has_src:
        return "declared S1+ but no source tree found"
    if stage_rank(declared) >= stage_rank(Stage.S2) and not _has_ci(repo):
        return "declared S2+ but no CI workflow present"
    if stage_rank(declared) >= stage_rank(Stage.S3) and not _has_integration_marker(repo):
        return "declared S3+ but no integration-test directory found"
    if declared is Stage.S4 and not _has_release_path(repo):
        return "declared S4 but no release pipeline or deployment manifest found"
    return None


def _ceiling_drift(repo: Repo, declared: Stage) -> str | None:
    """Ceiling signals: structure exceeds the declared stage (catches under-declaration)."""
    if stage_rank(declared) < stage_rank(Stage.S2) and _has_ci(repo):
        return f"declared {declared.value} but a CI workflow is present (looks S2+)"
    if stage_rank(declared) < stage_rank(Stage.S3) and _has_integration_marker(repo):
        return f"declared {declared.value} but integration tests are present (looks S3+)"
    if stage_rank(declared) < stage_rank(Stage.S4) and _has_release_path(repo):
        return f"declared {declared.value} but a release pipeline is present (looks S4)"
    return None


def drift_signal(repo: Repo, declared: Stage) -> str | None:
    """Return a one-line drift description when cheap signals contradict ``declared``.

    Coarse static checks only; catches obvious contradictions, not a full re-audit.
    """
    has_src = _has_source_tree(repo)
    floor = _floor_drift(repo, declared, has_src)
    if floor is not None:
        return floor
    return _ceiling_drift(repo, declared)
