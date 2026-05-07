"""Tests for the CLI entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check import repos as repos_mod
from consistency_check.__main__ import main
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_audit_no_apply_runs_without_gh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    fake = Repo(name="fake", path=tmp_path, language="python", github_slug="o/fake")
    monkeypatch.setattr(repos_mod, "REGISTRY", (fake,))

    rc = main(["audit", "--repo", "fake"])
    out = capsys.readouterr().out
    assert "fake" in out
    assert rc in (0, 1)


def test_unknown_repo_exits_with_code() -> None:
    rc = main(["audit", "--repo", "does-not-exist"])
    assert rc == 2
