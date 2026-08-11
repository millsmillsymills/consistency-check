"""Tests for the markdown report emitter."""

from __future__ import annotations

import pytest
from consistency_check.report import (
    render_child_issue,
    render_umbrella,
)
from consistency_check.types import Finding, FindingStatus, Stage, Tier


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


def _staged_findings() -> list[Finding]:
    return [
        Finding(rule_id="MCP-001", tier=Tier.MUST, status=FindingStatus.PASS, min_stage=Stage.S0),
        Finding(
            rule_id="MCP-014",
            tier=Tier.MUST,
            status=FindingStatus.NA,
            evidence="min_stage S2 above declared S1",
            min_stage=Stage.S2,
        ),
        Finding(
            rule_id="PROTO-001",
            tier=Tier.MUST,
            status=FindingStatus.FAIL,
            evidence="tool not snake_case",
            min_stage=Stage.S1,
        ),
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


def test_umbrella_unstaged_section() -> None:
    body = render_umbrella(repo_name="u", findings=_findings(), declared_stage=None)
    assert "## Stage" in body
    assert "Unstaged" in body


def test_umbrella_staged_section(snapshot) -> None:
    body = render_umbrella(repo_name="s", findings=_staged_findings(), declared_stage=Stage.S1)
    assert body == snapshot


def test_promotion_checklist_skips_other_language_rules() -> None:
    # A GO rule is n/a on a Python repo for good: promoting a stage will never
    # turn it into work, so it must not appear in the "To reach S2" list.
    findings = [
        *_staged_findings(),
        Finding(
            rule_id="GO-011",
            tier=Tier.MUST,
            status=FindingStatus.NA,
            min_stage=Stage.S2,
            applicable=False,
        ),
    ]
    body = render_umbrella(repo_name="s", findings=findings, declared_stage=Stage.S1)
    assert "To reach **S2**: MCP-014." in body


def _fail(evidence: str) -> Finding:
    return Finding(
        rule_id="PROTO-001", tier=Tier.MUST, status=FindingStatus.FAIL, evidence=evidence
    )


def _rendered_evidence(child: str) -> str:
    return child.split("**Evidence.** ", 1)[1].split("\n", 1)[0]


def test_long_evidence_is_truncated_in_both_renderings() -> None:
    # Evidence is a short token by convention, not by construction. An issue
    # body over the API limit aborts that repo's filing, so none of its child
    # issues are created.
    finding = _fail("x" * 5000)
    child = render_child_issue("unifi-mcp", finding)
    assert child is not None
    assert "… (truncated)" in child
    # Assert on the evidence segment: a bound on the whole body still passes if
    # the cap were raised, or if evidence were replaced by the marker alone.
    assert len(_rendered_evidence(child)) < 550
    assert "… (truncated)" in render_umbrella("unifi-mcp", [finding])


@pytest.mark.parametrize(
    ("length", "truncated"),
    [(499, False), (500, False), (501, True)],
)
def test_the_cap_boundary(length: int, truncated: bool) -> None:
    # Pins `<= _EVIDENCE_LIMIT` against an off-by-one in either direction.
    child = render_child_issue("unifi-mcp", _fail("x" * length))
    assert child is not None
    assert ("truncated" in child) is truncated


def test_short_evidence_is_left_alone() -> None:
    finding = _fail("non-snake_case tool names: ['Bad-Name']")
    child = render_child_issue("unifi-mcp", finding)
    assert child is not None
    assert "non-snake_case tool names: ['Bad-Name']" in child
    assert "truncated" not in child


def test_evidence_is_fenced_so_handles_do_not_become_mentions() -> None:
    # Filed against a public repo, a bare `@name` notifies whoever owns that
    # handle and a bare `#12` cross-references an unrelated issue.
    child = render_child_issue("unifi-mcp", _fail("tool @admin references #12"))
    assert child is not None
    assert "`tool @admin references #12`" in child


def test_evidence_containing_backticks_stays_inside_its_fence() -> None:
    child = render_child_issue("unifi-mcp", _fail("name is ``weird``"))
    assert child is not None
    assert _rendered_evidence(child) == "``` name is ``weird`` ```"


def test_errors_render_the_exception_type_without_the_traceback() -> None:
    # audit.py keeps the traceback off the finding for exactly this reason: the
    # rendered body is filed publicly and an exception message carries paths.
    errors = [
        Finding(rule_id="PY-001", tier=Tier.MUST, status=FindingStatus.ERROR, evidence="OSError"),
        Finding(rule_id="PY-002", tier=Tier.MUST, status=FindingStatus.ERROR),
    ]
    body = render_umbrella("unifi-mcp", errors)
    assert "## Audit errors (2)" in body
    assert "- **PY-001** — `OSError`" in body
    assert "- **PY-002** — `unknown`" in body
