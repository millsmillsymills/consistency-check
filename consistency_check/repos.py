"""Registry of MCP repositories audited by consistency-check."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Repo

_PROJECTS = Path.home() / "Desktop" / "Projects"

REGISTRY: tuple[Repo, ...] = (
    Repo(
        name="unifi-mcp",
        path=_PROJECTS / "unifi-mcp",
        language="python",
        github_slug="millsmillsymills/unifi-mcp",
    ),
    Repo(
        name="unraid-mcp",
        path=_PROJECTS / "unraid-mcp",
        language="python",
        github_slug="millsmillsymills/unraid-mcp",
    ),
    Repo(
        name="gandi-mcp",
        path=_PROJECTS / "gandi-mcp",
        language="python",
        github_slug="millsmillsymills/gandi-mcp",
    ),
    Repo(
        name="protonmail-mcp",
        path=_PROJECTS / "protonmail-mcp",
        language="go",
        github_slug="millsmillsymills/protonmail-mcp",
    ),
)
