"""Pin the min_stage assignment so it matches docs/standards/stages.md."""

from __future__ import annotations

from consistency_check.audit import all_rules
from consistency_check.types import Stage

_EXPECTED: dict[str, Stage] = {
    "MCP-001": Stage.S0,
    "MCP-002": Stage.S0,
    "MCP-005": Stage.S0,
    "MCP-006": Stage.S0,
    "MCP-007": Stage.S0,
    "MCP-009": Stage.S0,
    "MCP-010": Stage.S0,
    "MCP-019": Stage.S0,
    "MCP-020": Stage.S0,
    "PROTO-001": Stage.S1,
    "PROTO-002": Stage.S1,
    "PROTO-003": Stage.S1,
    "PROTO-004": Stage.S1,
    "PROTO-018": Stage.S1,
    "MCP-021": Stage.S1,
    "MCP-022": Stage.S1,
    "PROTO-005": Stage.S2,
    "PROTO-006": Stage.S2,
    "MCP-014": Stage.S2,
    "MCP-017": Stage.S2,
    "MCP-023": Stage.S2,
    "MCP-018": Stage.S4,
    "MCP-DEPLOY-ARTIFACT": Stage.S4,
    "MCP-DEPLOY-DOCS": Stage.S4,
    "MCP-DEPLOY-TRANSPORT": Stage.S4,
    "MCP-DEPLOY-REGISTRY": Stage.S4,
    "MCP-STAGE-DECL": Stage.S0,
    "MCP-STAGE-DRIFT": Stage.S0,
}


def test_min_stage_assignments_match_doc() -> None:
    by_id = {r.id: r for r in all_rules()}
    mismatches = {
        rid: (by_id[rid].min_stage, expected)
        for rid, expected in _EXPECTED.items()
        if by_id[rid].min_stage is not expected
    }
    assert not mismatches, f"min_stage mismatches (actual, expected): {mismatches}"


def test_unlisted_rules_default_to_s3() -> None:
    explicit = set(_EXPECTED)
    for rule in all_rules():
        if rule.id not in explicit:
            assert rule.min_stage is Stage.S3, f"{rule.id} should default to S3"
