"""Tests for the target repo registry."""

from __future__ import annotations

from consistency_check.repos import REGISTRY


def test_registry_lists_all_mcp_repos() -> None:
    names = {r.name for r in REGISTRY}
    assert names == {
        "unifi-mcp",
        "unraid-mcp",
        "gandi-mcp",
        "shortcut-mcp",
        "flipperzero-mcp",
        "protonmail-mcp",
    }


def test_registry_languages_correct() -> None:
    by_name = {r.name: r for r in REGISTRY}
    assert by_name["unifi-mcp"].language == "python"
    assert by_name["unraid-mcp"].language == "python"
    assert by_name["gandi-mcp"].language == "python"
    assert by_name["shortcut-mcp"].language == "python"
    assert by_name["flipperzero-mcp"].language == "python"
    assert by_name["protonmail-mcp"].language == "go"


def test_registry_github_slugs_under_org() -> None:
    for r in REGISTRY:
        assert r.github_slug == f"millsymills-com/{r.name}"
