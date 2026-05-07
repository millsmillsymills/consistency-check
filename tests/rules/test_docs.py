"""Tests for docs rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.docs import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    return next(r for r in RULES if r.id == rule_id).check(repo)


def test_mcp_007_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-007") is None


def test_mcp_007_fail_on_bad_python(bad_python_repo: Path) -> None:
    assert _check(bad_python_repo, "python", "MCP-007") is not None


def test_mcp_009_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-009") is None


def test_mcp_009_fail_when_claude_md_lacks_link(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("nothing useful\n", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    rule = next(r for r in RULES if r.id == "MCP-009")
    assert rule.check(repo) is not None
