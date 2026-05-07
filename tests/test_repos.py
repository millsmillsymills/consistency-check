"""Tests for the target repo registry."""

from __future__ import annotations

from consistency_check.repos import REGISTRY


def test_registry_lists_all_four_mcp_repos() -> None:
    names = {r.name for r in REGISTRY}
    assert names == {"unifi-mcp", "unraid-mcp", "gandi-mcp", "protonmail-mcp"}


def test_registry_languages_correct() -> None:
    by_name = {r.name: r for r in REGISTRY}
    assert by_name["unifi-mcp"].language == "python"
    assert by_name["unraid-mcp"].language == "python"
    assert by_name["gandi-mcp"].language == "python"
    assert by_name["protonmail-mcp"].language == "go"


def test_registry_github_slugs_present() -> None:
    for r in REGISTRY:
        assert "/" in r.github_slug
