"""Rules: top-level structure (MCP-001, MCP-002, MCP-005, MCP-006)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check._git import tracked_files
from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

_REQUIRED_TOP_LEVEL = ("README.md", "LICENSE", "CLAUDE.md", "SECURITY.md")
_FORBIDDEN_GLOBS = (
    "__pycache__",
    "*.pyc",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    ".venv",
    "node_modules",
)
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
_SPDX_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    "apache-2.0": (("apache-2.0",), ("apache license", "version 2.0")),
    "mit": (("mit license",), ("permission is hereby granted, free of charge",)),
    "bsd-3-clause": (("bsd 3-clause",), ("bsd-3-clause",), ("redistribution and use",)),
    "bsd-2-clause": (("bsd 2-clause",), ("bsd-2-clause",)),
    "gpl-3.0": (("gnu general public license", "version 3"), ("gpl-3.0",)),
    "isc": (("isc license",), ("permission to use, copy, modify",)),
    "mpl-2.0": (("mozilla public license", "version 2.0"), ("mpl-2.0",)),
}


def _license_matches(spdx: str, license_text: str) -> bool:
    text_lower = license_text.lower()
    alias_groups = _SPDX_ALIASES.get(spdx.lower())
    if alias_groups is None:
        return spdx.lower() in text_lower
    return any(all(token in text_lower for token in group) for group in alias_groups)


def _check_required_files(repo: Repo) -> str | None:
    missing = [f for f in _REQUIRED_TOP_LEVEL if not (repo.path / f).is_file()]
    if not missing:
        sec = (repo.path / "SECURITY.md").read_text(encoding="utf-8", errors="replace").lower()
        if not any(s in sec for s in ("reporting", "disclosure", "advisor")):
            return "SECURITY.md present but does not describe a disclosure path"
        return None
    return f"missing top-level files: {', '.join(missing)}"


def _check_license_spdx(repo: Repo) -> str | None:
    license_file = repo.path / "LICENSE"
    if not license_file.is_file():
        return "LICENSE missing"
    text = license_file.read_text(encoding="utf-8", errors="replace")
    if repo.language == "python":
        pyproject = repo.path / "pyproject.toml"
        if not pyproject.is_file():
            return None
        py = pyproject.read_text(encoding="utf-8")
        match = re.search(r'license\s*=\s*"([^"]+)"', py)
        if match and not _license_matches(match.group(1), text):
            return f"pyproject license {match.group(1)!r} not found in LICENSE text"
    return None


def _check_no_committed_artifacts(repo: Repo) -> str | None:
    tracked = tracked_files(repo.path)
    offenders: list[str] = []
    for pattern in _FORBIDDEN_GLOBS:
        for hit in repo.path.rglob(pattern):
            try:
                rel = hit.relative_to(repo.path)
            except ValueError:
                continue
            if any(part in _SKIP_DIRS for part in rel.parts):
                continue
            rel_str = rel.as_posix()
            if tracked and not _hit_is_tracked(rel_str, tracked):
                continue
            offenders.append(str(rel))
            if len(offenders) >= 5:
                break
        if len(offenders) >= 5:
            break
    return f"committed build artifacts: {', '.join(offenders)}" if offenders else None


def _hit_is_tracked(rel_str: str, tracked: frozenset[str]) -> bool:
    if rel_str in tracked:
        return True
    prefix = rel_str + "/"
    return any(t.startswith(prefix) for t in tracked)


def _check_gitignore(repo: Repo) -> str | None:
    gi = repo.path / ".gitignore"
    if not gi.is_file():
        return ".gitignore missing"
    contents = gi.read_text(encoding="utf-8")
    required = ("__pycache__", "*.pyc") if repo.language == "python" else ("*.test",)
    missing = [r for r in required if r not in contents]
    return f".gitignore missing entries: {', '.join(missing)}" if missing else None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-001",
        tier=Tier.MUST,
        statement="Top-level files: README.md, LICENSE, CLAUDE.md, SECURITY.md",
        check=_check_required_files,
    ),
    Rule(
        id="MCP-002",
        tier=Tier.MUST,
        statement="LICENSE matches declared SPDX identifier",
        check=_check_license_spdx,
    ),
    Rule(
        id="MCP-005",
        tier=Tier.MUST,
        statement="No build artifacts committed",
        check=_check_no_committed_artifacts,
    ),
    Rule(
        id="MCP-006",
        tier=Tier.MUST,
        statement=".gitignore excludes language-standard artifacts",
        check=_check_gitignore,
    ),
)
