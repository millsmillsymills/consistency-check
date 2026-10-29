"""Properties for dry-run isolation and issue-filing idempotency."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from consistency_check.filer import file_repo_findings
from consistency_check.types import Finding, FindingStatus, Repo, Tier
from hypothesis import given, settings
from hypothesis import strategies as st

_TIERS = st.sampled_from(list(Tier))
_STATUSES = st.sampled_from(list(FindingStatus))


@st.composite
def _findings(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    return [
        Finding(
            rule_id=f"MCP-{i:03d}",
            tier=draw(_TIERS),
            status=draw(_STATUSES),
            evidence=draw(st.text(max_size=40)),
        )
        for i in range(n)
    ]


@given(_findings())
@settings(max_examples=30, deadline=None)
def test_repeated_dry_runs_never_call_gh(findings) -> None:
    repo = Repo(name="r", path=Path("/tmp"), language="python", github_slug="o/r")  # noqa: S108

    with patch("consistency_check.filer.subprocess.run") as mock:
        file_repo_findings(repo, findings, apply=False)
        file_repo_findings(repo, findings, apply=False)

    assert mock.call_count == 0


class _FakeGitHub:
    """Persist issues between calls while exercising the real filer logic."""

    def __init__(self) -> None:
        self.issues: dict[str, str] = {}
        self.edited: list[str] = []

    def run(self, cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        operation = cmd[2]
        if operation == "list":
            issues = [
                {"number": i, "title": title, "state": "OPEN"}
                for i, title in enumerate(self.issues, start=1)
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(issues), stderr="")
        body = cmd[cmd.index("--body") + 1]
        if operation == "create":
            title = cmd[cmd.index("--title") + 1]
            assert title not in self.issues, f"duplicate issue created: {title}"
        else:
            assert operation == "edit"
            title = list(self.issues)[int(cmd[3]) - 1]
            self.edited.append(title)
        self.issues[title] = body
        return subprocess.CompletedProcess(
            cmd, 0, stdout="https://github.com/o/r/issues/1", stderr=""
        )


@given(_findings())
@settings(max_examples=30, deadline=None)
def test_double_apply_creates_each_issue_once_and_only_edits_umbrella(findings) -> None:
    repo = Repo(name="r", path=Path("/tmp"), language="python", github_slug="o/r")  # noqa: S108
    github = _FakeGitHub()
    failures = [f for f in findings if f.status is FindingStatus.FAIL]
    expected = {f"[consistency] r: {f.rule_id}" for f in failures if f.tier is not Tier.MAY}
    if failures:
        expected.add("[consistency] r: audit umbrella")

    with patch("consistency_check.filer.subprocess.run", side_effect=github.run):
        file_repo_findings(repo, findings, apply=True)
        first_bodies = github.issues.copy()
        file_repo_findings(repo, findings, apply=True)

    assert set(github.issues) == expected
    assert github.issues == first_bodies
    assert github.edited == (["[consistency] r: audit umbrella"] if failures else [])
