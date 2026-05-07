"""Tests for dependency and observability rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.deps import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language=lang, github_slug="x/y"),
    )


def test_mcp_021_pass_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-021") is None


def test_mcp_021_pass_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-021") is None


def test_mcp_023_pass_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-023") is None


def test_mcp_023_pass_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-023") is None


def test_mcp_023_fail_python_no_lock(good_python_repo: Path) -> None:
    (good_python_repo / "uv.lock").unlink()
    assert _check(good_python_repo, "python", "MCP-023") is not None
