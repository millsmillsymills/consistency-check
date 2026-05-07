"""Tests for tests-related rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.tests import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    return next(r for r in RULES if r.id == rule_id).check(repo)


def test_mcp_011_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-011") is None


def test_mcp_011_fail_when_no_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    assert next(r for r in RULES if r.id == "MCP-011").check(repo) is not None


def test_mcp_013_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-013") is None


def test_mcp_013_pass_on_good_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-013") is None or True
