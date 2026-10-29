"""Check every rule's stage against the authoritative standards table."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from consistency_check.audit import all_rules
from consistency_check.types import Stage

_STANDARDS = Path(__file__).resolve().parents[1] / "docs" / "standards" / "stages.md"
_RULE_ID = re.compile(r"[A-Z]+-(?:\d{3}|(?:STAGE|DEPLOY)-[A-Z]+)")


def _stage_rows(body: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in body.splitlines() if line.lstrip().startswith("|")]
    assert len(lines) == len(Stage) + 2, "min_stage map must have exactly one row for each stage"
    assert all(line.endswith("|") for line in lines), "stage table rows must end with a pipe"
    cells = [[cell.strip() for cell in line[1:-1].split("|")] for line in lines]
    assert all(len(row) == 2 for row in cells), "stage table rows must have two columns"
    assert cells[0] == ["min_stage", "Rules"], "stage table header is missing or malformed"
    assert all(re.fullmatch(r":?-+:?", cell) for cell in cells[1]), (
        "stage table separator is missing or malformed"
    )
    return [(row[0], row[1]) for row in cells[2:]]


def _documented_policy(text: str) -> tuple[dict[str, Stage], Stage]:
    section = re.search(r"(?ms)^## min_stage map\s*\n(.*?)(?=^## |\Z)", text)
    assert section is not None, "standards must contain a min_stage map section"
    body = section.group(1)
    closure = re.search(r"any rule not listed here defaults to `min_stage = (S[0-4])`", body)
    assert closure is not None, "standards must declare the default min_stage"
    default = Stage(closure.group(1))
    rows = _stage_rows(body)
    assert {stage for stage, _ in rows} == set(Stage), (
        "min_stage map must have exactly one row for each stage"
    )
    policy: dict[str, Stage] = {}
    default_rows = []
    for stage, cell in rows:
        if cell.strip("*() ") == "all rules not otherwise listed":
            default_rows.append(Stage(stage))
            continue
        for token in cell.split(","):
            rule_id = token.strip().strip("`")
            assert _RULE_ID.fullmatch(rule_id), f"invalid rule ID in stage map: {rule_id!r}"
            assert rule_id not in policy, f"duplicate rule ID in stage map: {rule_id}"
            policy[rule_id] = Stage(stage)
    assert default_rows == [default], "default table row must match the closure rule"
    return policy, default


def _assert_stages_match(text: str) -> None:
    policy, default = _documented_policy(text)
    rules = {rule.id: rule for rule in all_rules()}
    assert not (unknown := policy.keys() - rules.keys()), f"unknown documented rules: {unknown}"
    mismatches = {
        rule_id: (rule.min_stage, expected)
        for rule_id, rule in rules.items()
        if rule.min_stage is not (expected := policy.get(rule_id, default))
    }
    assert not mismatches, f"min_stage mismatches (actual, documented): {mismatches}"


def test_min_stage_assignments_match_doc() -> None:
    _assert_stages_match(_STANDARDS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rule_id", ["MCP-001", "MCP-STAGE-DECL", "MCP-DEPLOY-DRIFT"])
def test_docs_only_stage_change_is_detected(rule_id: str) -> None:
    text = _STANDARDS.read_text(encoding="utf-8")
    text = text.replace(f"{rule_id}, ", "", 1).replace("| S1 | ", f"| S1 | {rule_id}, ", 1)
    with pytest.raises(AssertionError, match=rule_id):
        _assert_stages_match(text)


def test_docs_only_default_change_is_detected() -> None:
    text = _STANDARDS.read_text(encoding="utf-8")
    text = text.replace("`min_stage = S3`", "`min_stage = S2`")
    text = text.replace("| S2 |", "| TEMP |").replace("| S3 |", "| S2 |")
    text = text.replace("| TEMP |", "| S3 |")
    with pytest.raises(AssertionError, match="GO-001"):
        _assert_stages_match(text)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("| S0 |", "| S5 |", "one row for each stage"),
        ("| S1 |", "| S0 |", "one row for each stage"),
        ("| S1 | ", "| S1 | MCP-001, ", "duplicate rule ID"),
        ("| S1 | ", "| S1 | UNKNOWN-999, ", "unknown documented rules"),
        ("| S1 | ", "| S1 | malformed, ", "invalid rule ID"),
        ("`min_stage = S3`", "`min_stage = S2`", "default table row"),
        ("## min_stage map", "## missing map", "min_stage map section"),
    ],
)
def test_invalid_documented_policy_cannot_silently_pass(old: str, new: str, message: str) -> None:
    text = _STANDARDS.read_text(encoding="utf-8").replace(old, new, 1)
    with pytest.raises(AssertionError, match=message):
        _assert_stages_match(text)


@pytest.mark.parametrize(
    "row",
    ["| S5 | MCP-001 |", "| invalid | MCP-001 |", "| S5 | MCP-001 | extra |"],
)
def test_extra_invalid_table_rows_are_rejected(row: str) -> None:
    text = _STANDARDS.read_text(encoding="utf-8").replace("| S3 |", f"{row}\n| S3 |", 1)
    with pytest.raises(AssertionError):
        _assert_stages_match(text)


def test_default_row_cannot_hide_explicit_rule_assignments() -> None:
    text = _STANDARDS.read_text(encoding="utf-8").replace(
        "*(all rules not otherwise listed)*", "*(all rules not otherwise listed)*, MCP-001"
    )
    with pytest.raises(AssertionError):
        _assert_stages_match(text)
