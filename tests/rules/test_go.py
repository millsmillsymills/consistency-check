"""Tests for GO-* rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.go import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="go", github_slug="x/y"),
    )


def test_go_001_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-001") is None


def test_go_004_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-004") is None


def test_go_004_fail_when_no_golangci(good_go_repo: Path) -> None:
    (good_go_repo / ".golangci.yml").unlink()
    assert _check(good_go_repo, "GO-004") is not None


def test_go_012_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-012") is None


def test_go_012_fail_when_mcp_go_missing(good_go_repo: Path) -> None:
    (good_go_repo / "go.mod").write_text("module foo\ngo 1.22\n", encoding="utf-8")
    assert _check(good_go_repo, "GO-012") is not None
