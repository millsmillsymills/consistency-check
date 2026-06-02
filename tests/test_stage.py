"""Tests for stage parsing, SCOPE.md parsing, and drift signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.stage import declared_stage, next_stage, stage_rank
from consistency_check.types import Repo, Stage

if TYPE_CHECKING:
    from pathlib import Path


def _repo(root: Path, language: str = "python") -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _write_readme(root: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(body, encoding="utf-8")


def test_declared_stage_reads_token_from_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nAlpha. Stage: S2.\n\n## License\nMIT\n")
    assert declared_stage(_repo(tmp_path)) is Stage.S2


def test_declared_stage_is_none_when_no_token(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nUnder active development.\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_is_none_without_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## License\nMIT\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_is_none_when_readme_missing(tmp_path: Path) -> None:
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_ignores_token_outside_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nAlpha.\n\n## Notes\nSee S3 spec.\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_stage_rank_orders_s0_below_s4() -> None:
    assert stage_rank(Stage.S0) < stage_rank(Stage.S2) < stage_rank(Stage.S4)


def test_next_stage_returns_successor_and_none_at_top() -> None:
    assert next_stage(Stage.S2) is Stage.S3
    assert next_stage(Stage.S4) is None
