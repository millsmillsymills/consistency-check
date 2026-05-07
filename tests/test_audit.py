"""Tests for the audit driver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import consistency_check.audit as audit_mod
from consistency_check.audit import all_rules, audit_repo
from consistency_check.types import FindingStatus, Repo, Rule, Tier

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
