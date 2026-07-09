"""Tests for stage parsing, SCOPE.md parsing, and drift signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.stage import (
    declared_stage,
    drift_signal,
    has_scope_exception,
    next_stage,
    stage_rank,
    surface_operations,
)
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


def test_surface_operations_parses_bullets(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text(
        "# Scope\n\n## Surface\n- list_devices\n- create_wlan\n\n## Auth\nAPI key.\n",
        encoding="utf-8",
    )
    assert surface_operations(_repo(tmp_path)) == ["list_devices", "create_wlan"]


def test_surface_operations_empty_without_scope_file(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert surface_operations(_repo(tmp_path)) == []


def test_has_scope_exception_detects_heading(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text(
        "## Surface\n- x\n\n## Scope exception\nWLAN only; rest out of scope.\n",
        encoding="utf-8",
    )
    assert has_scope_exception(_repo(tmp_path)) is True


def test_has_scope_exception_false_without_heading(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text("## Surface\n- x\n", encoding="utf-8")
    assert has_scope_exception(_repo(tmp_path)) is False


def test_drift_s0_with_src_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    assert drift_signal(_repo(tmp_path), Stage.S0) is not None


def test_drift_s1_without_src_tree(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert drift_signal(_repo(tmp_path), Stage.S1) is not None


def test_drift_s2_without_ci(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    assert drift_signal(_repo(tmp_path), Stage.S2) is not None


def test_no_drift_for_staged_s2_repo(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    assert drift_signal(_repo(tmp_path), Stage.S2) is None


def test_drift_go_source_tree_accepts_cmd(tmp_path: Path) -> None:
    (tmp_path / "cmd").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    assert drift_signal(_repo(tmp_path, language="go"), Stage.S2) is None


def test_drift_ceiling_ci_below_s2(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    # Declared S1 but CI present -> looks like S2+.
    assert drift_signal(_repo(tmp_path), Stage.S1) is not None


def test_drift_ceiling_integration_below_s3(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "tests" / "integration").mkdir(parents=True)
    # Declared S2 but integration tests present -> looks like S3+.
    assert drift_signal(_repo(tmp_path), Stage.S2) is not None
