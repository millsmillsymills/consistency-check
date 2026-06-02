"""Tests for the audit driver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import consistency_check.audit as audit_mod
from consistency_check.audit import all_rules, audit_repo
from consistency_check.stage import stage_rank
from consistency_check.types import FindingStatus, Repo, Rule, Stage, Tier

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_all_rules_loaded() -> None:
    rules = all_rules()
    ids = {r.id for r in rules}
    assert "MCP-001" in ids
    assert "PY-001" in ids
    assert "GO-001" in ids
    assert "PROTO-001" in ids
    assert len(rules) >= 60


def test_audit_repo_runs_only_applicable_rules(good_python_repo: Path) -> None:
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    statuses = {f.status for f in findings}
    assert FindingStatus.PASS in statuses


def test_audit_repo_isolates_rule_crashes(
    good_python_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_repo: Repo) -> str | None:
        raise RuntimeError("boom")

    bad_rule = Rule(id="X-999", tier=Tier.MUST, statement="boom", check=boom)
    monkeypatch.setattr(audit_mod, "all_rules", lambda: [bad_rule])
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    assert any(f.status == FindingStatus.ERROR for f in findings)


def test_above_stage_rules_recorded_na(tmp_path: Path) -> None:
    root = tmp_path / "staged"
    root.mkdir()
    # Minimal repo declared S0: only S0 rules should be evaluated; higher ones NA.
    (root / "README.md").write_text("# x\n\n## Status\nStage: S0.\n", encoding="utf-8")
    repo = Repo(name="staged", path=root, language="python", github_slug="x/y")

    findings = audit_repo(repo)
    by_id = {f.rule_id: f for f in findings}
    # A MUST rule above S0 (e.g. MCP-014 at S2) must be skipped as n/a.
    assert by_id["MCP-014"].status == FindingStatus.NA
    assert stage_rank(by_id["MCP-014"].min_stage) > stage_rank(Stage.S0)


def test_unstaged_repo_runs_all_rules(
    good_python_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force unstaged regardless of fixture README.
    monkeypatch.setattr(audit_mod, "declared_stage", lambda _r: None)
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    # No finding is skipped for being above-stage when unstaged.
    above = [
        f for f in findings if f.status == FindingStatus.NA and f.evidence.startswith("min_stage")
    ]
    assert not above
