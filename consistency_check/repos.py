"""Registry of MCP repositories audited by consistency-check."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Repo

_PROJECTS = Path.home() / "Desktop" / "Projects" / "mcp-server-dev"
_ORG = "millsymills-com"


def _repo(name: str, language: str) -> Repo:
    return Repo(
        name=name,
        path=_PROJECTS / name,
        language=language,
        github_slug=f"{_ORG}/{name}",
    )


REGISTRY: tuple[Repo, ...] = (
    _repo("unifi-mcp", "python"),
    _repo("unraid-mcp", "python"),
    _repo("gandi-mcp", "python"),
    _repo("shortcut-mcp", "python"),
    _repo("flipperzero-mcp", "python"),
    _repo("protonmail-mcp", "go"),
)
