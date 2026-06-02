"""Tests for core dataclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import Finding, FindingStatus, Repo, Rule, Stage, Tier

if TYPE_CHECKING:
    from pathlib import Path


def test_rule_default_applies_to_is_all_languages() -> None:
    rule = Rule(id="MCP-001", tier=Tier.MUST, statement="x", check=lambda _repo: None)
    assert rule.applies_to == frozenset({"python", "go"})


def test_finding_status_enum_has_required_members() -> None:
    assert {s.value for s in FindingStatus} == {"pass", "fail", "n/a", "error"}


def test_repo_dataclass_is_frozen(tmp_path: Path) -> None:
    repo = Repo(name="x", path=tmp_path / "x", language="python", github_slug="o/x")
    try:
        repo.name = "y"  # type: ignore[misc]  # ty: ignore[invalid-assignment]
    except Exception:  # noqa: BLE001
        return
    raise AssertionError("Repo should be frozen")


def test_stage_enum_values() -> None:
    assert [s.value for s in Stage] == ["S0", "S1", "S2", "S3", "S4"]


def test_rule_min_stage_defaults_to_s3() -> None:
    rule = Rule(id="X-001", tier=Tier.MUST, statement="x", check=lambda _r: None)
    assert rule.min_stage is Stage.S3


def test_finding_min_stage_defaults_to_s3() -> None:
    finding = Finding(rule_id="X-001", tier=Tier.MUST, status=FindingStatus.PASS)
    assert finding.min_stage is Stage.S3
