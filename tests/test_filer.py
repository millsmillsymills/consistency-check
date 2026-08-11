"""Tests for the gh-CLI filer."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from consistency_check.filer import file_repo_findings, gh_auth_ok
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
    with patch(
        "consistency_check.filer.subprocess.run",
        side_effect=[
            _run(0, json.dumps([])),  # gh auth status
            _run(0, json.dumps([])),  # search existing umbrellas
            _run(0, "https://github.com/o/good/issues/1\n"),  # create umbrella
            _run(0, json.dumps([])),  # search existing child for MCP-007
            _run(0, "https://github.com/o/good/issues/2\n"),  # create child
        ],
    ) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [
        c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]
    ]
    assert len(create_calls) == 2  # umbrella + 1 child (MAY skipped)


def test_apply_skips_existing_open_issue(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    existing = json.dumps([{"number": 5, "title": "[consistency] good: MCP-007", "state": "OPEN"}])
    with patch(
        "consistency_check.filer.subprocess.run",
        side_effect=[
            _run(0),  # auth
            _run(
                0,
                json.dumps(
                    [  # umbrella exists
                        {
                            "number": 4,
                            "title": "[consistency] good: audit umbrella",
                            "state": "OPEN",
                        },
                    ]
                ),
            ),
            _run(0),  # update umbrella body
            _run(0, existing),  # child exists
        ],
    ) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [
        c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]
    ]
    assert len(create_calls) == 0


def test_every_gh_call_passes_a_timeout(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with patch(
        "consistency_check.filer.subprocess.run",
        side_effect=[
            _run(0, json.dumps([])),  # gh auth status
            _run(0, json.dumps([])),  # search existing umbrellas
            _run(0, "https://github.com/o/good/issues/1\n"),  # create umbrella
            _run(0, json.dumps([])),  # search existing child
            _run(0, "https://github.com/o/good/issues/2\n"),  # create child
        ],
    ) as mock:
        file_repo_findings(repo, findings, apply=True)
    assert mock.call_count == 5
    for call in mock.call_args_list:
        assert call.kwargs["timeout"] > 0


def test_gh_auth_ok_is_true_only_on_success() -> None:
    with patch("consistency_check.filer.subprocess.run", return_value=_run(0)):
        assert gh_auth_ok() is True
    with patch("consistency_check.filer.subprocess.run", return_value=_run(1)):
        assert gh_auth_ok() is False


def test_hung_auth_check_reports_the_hang_not_a_stale_login(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with (
        patch(
            "consistency_check.filer.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30),
        ),
        pytest.raises(RuntimeError, match="timed out after"),
    ):
        file_repo_findings(repo, findings, apply=True)


def test_missing_gh_binary_is_reported_at_the_auth_gate(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with (
        patch(
            "consistency_check.filer.subprocess.run",
            side_effect=FileNotFoundError("gh"),
        ),
        pytest.raises(RuntimeError, match="could not be executed"),
    ):
        file_repo_findings(repo, findings, apply=True)


def test_hung_issue_call_raises_runtime_error(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with (
        patch(
            "consistency_check.filer.subprocess.run",
            side_effect=[
                _run(0),  # auth succeeds
                subprocess.TimeoutExpired(cmd="gh", timeout=30),  # issue list hangs
            ],
        ),
        pytest.raises(RuntimeError, match="issue list timed out"),
    ):
        file_repo_findings(repo, findings, apply=True)


def test_unauthenticated_gh_still_suggests_login(repo: Repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with (
        patch("consistency_check.filer.subprocess.run", return_value=_run(1)),
        pytest.raises(RuntimeError, match="gh auth login"),
    ):
        file_repo_findings(repo, findings, apply=True)
