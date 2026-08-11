"""An unevaluated MUST must reach the reader and the exit code, not read as a pass."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check import repos as repos_mod
from consistency_check.__main__ import main
from consistency_check._git import tracked_files
from consistency_check.audit import audit_repo
from consistency_check.report import render_umbrella
from consistency_check.rules.security import RULES as SECURITY_RULES
from consistency_check.rules.structure import RULES as STRUCTURE_RULES
from consistency_check.types import (
    Finding,
    FindingStatus,
    NotApplicable,
    Repo,
    Rule,
    Stage,
    Tier,
)

if TYPE_CHECKING:
    from pathlib import Path

_TRACKED_CONTENT_RULES: tuple[tuple[str, tuple[Rule, ...]], ...] = (
    ("MCP-019", SECURITY_RULES),
    ("MCP-005", STRUCTURE_RULES),
)


def _repo(path: Path) -> Repo:
    return Repo(name=path.name, path=path, language="python", github_slug="o/x")


def test_tracked_files_returns_none_without_git(tmp_path: Path) -> None:
    assert tracked_files(tmp_path) is None


def test_tracked_files_returns_none_when_git_metadata_is_broken(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /nowhere/that/exists\n", encoding="utf-8")
    assert tracked_files(tmp_path) is None


@pytest.mark.parametrize(("rule_id", "rules"), _TRACKED_CONTENT_RULES)
def test_tracked_content_rules_report_na_without_git(
    tmp_path: Path, rule_id: str, rules: tuple[Rule, ...]
) -> None:
    """A committed secret must not be scored either way when git cannot be asked."""
    (tmp_path / ".env").write_text("TOKEN=abc\n", encoding="utf-8")
    rule = next(r for r in rules if r.id == rule_id)
    result = rule.check(_repo(tmp_path))
    assert isinstance(result, NotApplicable)
    assert not result.unmechanized


def test_na_reason_carries_no_local_path(tmp_path: Path) -> None:
    rule = next(r for r in SECURITY_RULES if r.id == "MCP-019")
    result = rule.check(_repo(tmp_path))
    assert isinstance(result, NotApplicable)
    assert str(tmp_path) not in result.reason


def test_ungraded_must_is_rendered_not_silently_counted() -> None:
    findings = [
        Finding(
            rule_id="MCP-019",
            tier=Tier.MUST,
            status=FindingStatus.NA,
            evidence="git unavailable; cannot tell tracked files from working-tree files",
            min_stage=Stage.S0,
            unevaluated=True,
        )
    ]
    body = render_umbrella("x", findings, declared_stage=Stage.S3)
    assert "## Unevaluated (1)" in body
    assert "MCP-019" in body
    assert "compliant through S3 gates" not in body


def test_unmechanized_rules_are_reported_separately() -> None:
    findings = [
        Finding(
            rule_id="MCP-024",
            tier=Tier.SHOULD,
            status=FindingStatus.NA,
            evidence="dependency freshness needs network access; the audit runs offline",
            unevaluated=True,
            unmechanized=True,
        )
    ]
    body = render_umbrella("x", findings, declared_stage=None)
    assert "No checker written (1)" in body
    assert "Could not be checked" not in body


def test_unmechanized_rule_stays_off_the_promotion_checklist() -> None:
    findings = [
        Finding(
            rule_id="MCP-024",
            tier=Tier.SHOULD,
            status=FindingStatus.NA,
            evidence="the audit runs offline",
            min_stage=Stage.S3,
            unevaluated=True,
            unmechanized=True,
        )
    ]
    assert "To reach **S3**" not in render_umbrella("x", findings, declared_stage=Stage.S2)


def test_ungraded_must_escalates_the_exit_code(
    monkeypatch: pytest.MonkeyPatch, good_python_repo: Path, tmp_path: Path
) -> None:
    """The repo passes every rule it can be graded on; an ungraded rule is not a pass."""
    monkeypatch.setattr(
        "consistency_check.rules.security.tracked_files", lambda _p: None, raising=True
    )
    monkeypatch.setattr(
        "consistency_check.rules.structure.tracked_files", lambda _p: None, raising=True
    )
    repo = Repo(name="clean", path=good_python_repo, language="python", github_slug="o/clean")
    monkeypatch.setattr(repos_mod, "REGISTRY", (repo,))

    findings = audit_repo(repo)
    ungraded = [f for f in findings if f.unevaluated and not f.unmechanized and f.tier == Tier.MUST]
    assert ungraded

    assert main(["audit", "--repo", "clean", "--out", str(tmp_path / "reports")]) == 2
