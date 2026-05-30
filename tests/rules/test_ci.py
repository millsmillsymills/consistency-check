"""Tests for CI rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.ci import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language=lang, github_slug="x/y"),
    )


def test_mcp_014_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-014") is None


def test_mcp_017_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-017") is None


def test_mcp_017_fail_on_unpinned_action(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace(
            "actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7",
            "actions/checkout@v4",
        ),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-017") is not None
