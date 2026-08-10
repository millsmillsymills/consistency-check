"""Tests for the CLI entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check import __main__ as main_mod
from consistency_check import audit as audit_mod
from consistency_check import repos as repos_mod
from consistency_check.__main__ import main
from consistency_check.types import Repo, Rule, Tier

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


def test_out_dir_gets_one_report_per_repo(
    monkeypatch: pytest.MonkeyPatch,
    good_python_repo: Path,
    tmp_path: Path,
) -> None:
    clean = Repo(name="clean", path=good_python_repo, language="python", github_slug="o/clean")
    broken = Repo(name="broken", path=tmp_path / "empty", language="python", github_slug="o/broken")
    (tmp_path / "empty").mkdir()
    # Failing repo first, so a "last repo wins" aggregation would return 0.
    monkeypatch.setattr(repos_mod, "REGISTRY", (broken, clean))
    out = tmp_path / "reports"

    rc = main(["audit", "--out", str(out)])

    assert sorted(p.name for p in out.iterdir()) == ["broken.md", "clean.md"]
    # The exit code is the worst outcome across every repo, not the last one's.
    assert rc == 1


def test_rule_crash_exits_two(
    monkeypatch: pytest.MonkeyPatch,
    good_python_repo: Path,
    tmp_path: Path,
) -> None:
    def boom(_repo: Repo) -> str | None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        audit_mod,
        "all_rules",
        lambda: [Rule(id="X-999", tier=Tier.MUST, statement="boom", check=boom)],
    )
    repo = Repo(name="crashy", path=good_python_repo, language="python", github_slug="o/crashy")
    monkeypatch.setattr(repos_mod, "REGISTRY", (repo,))

    assert main(["audit", "--out", str(tmp_path / "reports")]) == 2


def test_filer_error_exits_three(
    monkeypatch: pytest.MonkeyPatch,
    good_python_repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("gh not authenticated")

    monkeypatch.setattr(main_mod, "file_repo_findings", explode)
    repo = Repo(name="clean", path=good_python_repo, language="python", github_slug="o/clean")
    monkeypatch.setattr(repos_mod, "REGISTRY", (repo,))

    rc = main(["audit", "--out", str(tmp_path / "reports")])

    assert rc == 3
    assert "gh not authenticated" in capsys.readouterr().err
