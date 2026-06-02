"""Rules: security (MCP-019, 020)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check._git import tracked_files
from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

_FORBIDDEN_NAMES = (".env", "credentials.json", "secrets.json", "id_rsa", "private.pem")
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".consistency-cache",
        ".worktrees",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        ".pytest_cache",
        ".ruff_cache",
        ".ty_cache",
        ".tox",
        "build",
    }
)


def _outside_skipped_dirs(hit: Path, repo_root: Path) -> bool:
    try:
        rel_parts = hit.relative_to(repo_root).parts
    except ValueError:
        return False
    return not any(part in _SKIP_DIRS for part in rel_parts)


def _check_no_secrets(repo: Repo) -> str | None:
    tracked = tracked_files(repo.path)
    candidates: list[Path] = []
    for name in _FORBIDDEN_NAMES:
        candidates.extend(repo.path.rglob(name))
    candidates.extend(repo.path.rglob("*.pem"))
    candidates.extend(repo.path.rglob("*.key"))

    offenders: list[str] = []
    for hit in candidates:
        if not _outside_skipped_dirs(hit, repo.path):
            continue
        rel = hit.relative_to(repo.path).as_posix()
        if tracked and rel not in tracked:
            continue
        offenders.append(rel)
    return f"secrets-shaped files in tree: {offenders[:5]}" if offenders else None


def _check_security_disclosure(repo: Repo) -> str | None:
    sec = repo.path / "SECURITY.md"
    if not sec.is_file():
        return "SECURITY.md missing"
    text = sec.read_text(encoding="utf-8", errors="replace").lower()
    if "@" not in text and "advisor" not in text and "disclosure" not in text:
        return "SECURITY.md does not describe a private disclosure path"
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-019",
        tier=Tier.MUST,
        statement="No secrets in tracked files",
        check=_check_no_secrets,
        min_stage=Stage.S0,
    ),
    Rule(
        id="MCP-020",
        tier=Tier.MUST,
        statement="SECURITY.md describes disclosure path",
        check=_check_security_disclosure,
        min_stage=Stage.S0,
    ),
)
