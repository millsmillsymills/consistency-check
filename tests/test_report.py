"""Tests for the markdown report emitter."""

from __future__ import annotations

from consistency_check.report import (
    render_child_issue,
    render_umbrella,
)
from consistency_check.types import Finding, FindingStatus, Tier


def _findings() -> list[Finding]:
    return [
        Finding(rule_id="MCP-001", tier=Tier.MUST, status=FindingStatus.PASS),
        Finding(
            rule_id="MCP-007",
            tier=Tier.MUST,
            status=FindingStatus.FAIL,
            evidence="README missing 'Configuration'",
        ),
        Finding(
            rule_id="MCP-018", tier=Tier.MAY, status=FindingStatus.FAIL, evidence="no release.yml"
        ),
        Finding(rule_id="GO-001", tier=Tier.MUST, status=FindingStatus.NA),
    ]


def test_umbrella_lists_failures_grouped_by_tier(snapshot) -> None:
    body = render_umbrella(repo_name="good", findings=_findings())
    assert body == snapshot


def test_child_issue_only_for_must_or_should(snapshot) -> None:
    must_fail = next(f for f in _findings() if f.rule_id == "MCP-007")
    body = render_child_issue(repo_name="good", finding=must_fail)
    assert body == snapshot


def test_child_issue_returns_none_for_may_failures() -> None:
    may_fail = next(f for f in _findings() if f.rule_id == "MCP-018")
    assert render_child_issue(repo_name="good", finding=may_fail) is None
