"""Rules: top-level structure (MCP-001, MCP-002, MCP-005, MCP-006)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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
        if match and match.group(1).lower() not in text.lower():
            return f"pyproject license {match.group(1)!r} not found in LICENSE text"
    return None


def _check_no_committed_artifacts(repo: Repo) -> str | None:
    offenders: list[str] = []
    for pattern in _FORBIDDEN_GLOBS:
        for hit in repo.path.rglob(pattern):
            if ".git" in hit.parts or ".consistency-cache" in hit.parts:
                continue
            offenders.append(str(hit.relative_to(repo.path)))
            if len(offenders) >= 5:
                break
        if len(offenders) >= 5:
            break
    return f"committed build artifacts: {', '.join(offenders)}" if offenders else None


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
