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


def test_mcp_021_ignores_go_sources_the_repo_does_not_own(tmp_path: Path) -> None:
    # A stale worktree copy or a test helper must not satisfy the rule on the
    # server's behalf: routing through go_sources is what applies the exclusions.
    (tmp_path / ".worktrees" / "old").mkdir(parents=True)
    (tmp_path / ".worktrees" / "old" / "main.go").write_text(
        'package main\nimport "os"\nfunc main() { os.Stderr.WriteString("x") }\n',
        encoding="utf-8",
    )
    (tmp_path / "main_test.go").write_text(
        'package main\nimport "os"\nfunc TestX() { os.Stderr.WriteString("x") }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "MCP-021") is not None


def test_mcp_022_ignores_go_sources_the_repo_does_not_own(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "pkg").mkdir(parents=True)
    (tmp_path / ".venv" / "pkg" / "dep.go").write_text(
        'package pkg\nimport "log/slog"\nvar _ = slog.Default\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "MCP-022") is not None


def test_mcp_023_pass_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-023") is None


def test_mcp_023_pass_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-023") is None


def test_mcp_023_fail_python_no_lock(good_python_repo: Path) -> None:
    (good_python_repo / "uv.lock").unlink()
    assert _check(good_python_repo, "python", "MCP-023") is not None
