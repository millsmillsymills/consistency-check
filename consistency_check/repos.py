"""Registry of MCP repositories audited by consistency-check."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Repo

_MCP_DEV = Path.home() / "Desktop" / "Projects" / "mcp-server-dev"

REGISTRY: tuple[Repo, ...] = (
    Repo(
        name="unifi-mcp",
        path=_MCP_DEV / "unifi-mcp",
        language="python",
        github_slug="millsymills-com/unifi-mcp",
    ),
    Repo(
        name="unraid-mcp",
        path=_MCP_DEV / "unraid-mcp",
        language="python",
        github_slug="millsymills-com/unraid-mcp",
    ),
    Repo(
        name="gandi-mcp",
        path=_MCP_DEV / "gandi-mcp",
        language="python",
        github_slug="millsymills-com/gandi-mcp",
    ),
    Repo(
        name="protonmail-mcp",
        path=_MCP_DEV / "protonmail-mcp",
        language="go",
        github_slug="millsymills-com/protonmail-mcp",
    ),
    Repo(
        name="shortcut-mcp",
        path=_MCP_DEV / "shortcut-mcp",
        language="python",
        github_slug="millsymills-com/shortcut-mcp",
    ),
    Repo(
        name="flipperzero-mcp",
        path=_MCP_DEV / "flipperzero-mcp",
        language="python",
        github_slug="millsymills-com/flipperzero-mcp",
    ),
)
