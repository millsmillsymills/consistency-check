"""Tests for the stage meta-rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.stage_meta import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path

_BY_ID = {r.id: r for r in RULES}


def _repo(root: Path) -> Repo:
    return Repo(name=root.name, path=root, language="python", github_slug="x/y")


def test_decl_fails_when_unstaged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nAlpha.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DECL"].check(_repo(tmp_path)) is not None


def test_decl_passes_when_staged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S1.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DECL"].check(_repo(tmp_path)) is None


def test_drift_passes_when_unstaged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nAlpha.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DRIFT"].check(_repo(tmp_path)) is None


def test_drift_fires_on_s0_with_src(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S0.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    assert _BY_ID["MCP-STAGE-DRIFT"].check(_repo(tmp_path)) is not None
