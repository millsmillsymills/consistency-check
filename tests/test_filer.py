"""Tests for the gh-CLI filer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from consistency_check.filer import file_repo_findings
from consistency_check.types import Finding, FindingStatus, Repo, Tier

if TYPE_CHECKING:
    from pathlib import Path



@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(name="good", path=tmp_path, language="python", github_slug="o/good")


def _run(returncode: int, stdout: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr="")


def test_dry_run_prints_no_gh_calls(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with patch("consistency_check.filer.subprocess.run") as mock:
        file_repo_findings(repo, findings, apply=False)
    assert mock.call_count == 0
    captured = capsys.readouterr().out
    assert "would call: gh issue create" in captured


def test_apply_creates_umbrella_then_children(repo: Repo) -> None:
    findings = [
        Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x"),
        Finding(rule_id="MCP-018", tier=Tier.MAY, status=FindingStatus.FAIL, evidence="z"),
    ]
    with patch("consistency_check.filer.subprocess.run", side_effect=[
        _run(0, json.dumps([])),  # gh auth status
        _run(0, json.dumps([])),  # search existing umbrellas
        _run(0, "https://github.com/o/good/issues/1\n"),  # create umbrella
        _run(0, json.dumps([])),  # search existing child for MCP-007
        _run(0, "https://github.com/o/good/issues/2\n"),  # create child
    ]) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [
        c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]
    ]
    assert len(create_calls) == 2  # umbrella + 1 child (MAY skipped)


def test_apply_skips_existing_open_issue(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    existing = json.dumps([{"number": 5, "title": "[consistency] good: MCP-007", "state": "OPEN"}])
    with patch("consistency_check.filer.subprocess.run", side_effect=[
        _run(0),  # auth
        _run(0, json.dumps([  # umbrella exists
            {"number": 4, "title": "[consistency] good: audit umbrella", "state": "OPEN"},
        ])),
        _run(0),  # update umbrella body
        _run(0, existing),  # child exists
    ]) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [
        c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]
    ]
    assert len(create_calls) == 0
