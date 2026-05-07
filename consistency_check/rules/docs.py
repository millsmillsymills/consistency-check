"""Rules: documentation (MCP-003, 004, 007, 008, 009, 010)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

_README_GROUPS = (
    {"status"},
    {"quick start", "install"},
    {"configuration", "environment variables"},
    {"development"},
    {"license"},
)
_CLIENT_NAMES = ("Claude Desktop", "Cursor", "Continue.dev", "Claude Code")
_STANDARDS_LINK = "consistency-check/docs/standards"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _h2s(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"(?m)^##\s+(.+?)\s*$", text)}


def _check_changelog(repo: Repo) -> str | None:
    cl = repo.path / "CHANGELOG.md"
    if not cl.is_file():
        return "CHANGELOG.md missing"
    text = _read(cl)
    if not re.search(r"(?m)^##\s+\[(Unreleased|\d+\.\d+\.\d+)\]", text):
        return "CHANGELOG.md does not use Keep-a-Changelog headings"
    return None


def _check_contributing(repo: Repo) -> str | None:
    return None if (repo.path / "CONTRIBUTING.md").is_file() else "CONTRIBUTING.md missing"


def _check_readme_sections(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md").lower()
    if not text:
        return "README.md missing"
    found = _h2s(text)
    missing_groups = [g for g in _README_GROUPS if not (g & found)]
    if missing_groups:
        return f"README missing required sections: {[sorted(g) for g in missing_groups]}"
    return None


def _check_readme_clients(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md")
    if any(name in text for name in _CLIENT_NAMES):
        return None
    return (
        "README does not declare any MCP client setup"
        " (Claude Desktop, Cursor, Continue.dev, Claude Code)"
    )


def _check_claude_md_link(repo: Repo) -> str | None:
    text = _read(repo.path / "CLAUDE.md")
    if _STANDARDS_LINK in text:
        return None
    return f"CLAUDE.md does not reference {_STANDARDS_LINK}"


def _check_docs_dir(repo: Repo) -> str | None:
    docs = repo.path / "docs"
    if not docs.is_dir():
        return "docs/ directory missing"
    if not any(docs.rglob("*.md")):
        return "docs/ contains no markdown"
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-003",
        tier=Tier.SHOULD,
        statement="CHANGELOG.md present, Keep-a-Changelog format",
        check=_check_changelog,
    ),
    Rule(
        id="MCP-004",
        tier=Tier.SHOULD,
        statement="CONTRIBUTING.md present",
        check=_check_contributing,
    ),
    Rule(
        id="MCP-007",
        tier=Tier.MUST,
        statement="README has required sections",
        check=_check_readme_sections,
    ),
    Rule(
        id="MCP-008",
        tier=Tier.SHOULD,
        statement="README declares MCP client setup",
        check=_check_readme_clients,
    ),
    Rule(
        id="MCP-009",
        tier=Tier.MUST,
        statement="CLAUDE.md references canonical standards",
        check=_check_claude_md_link,
    ),
    Rule(
        id="MCP-010",
        tier=Tier.SHOULD,
        statement="docs/ exists with markdown content",
        check=_check_docs_dir,
    ),
)
