"""Property: dry-run invocation is stable across repeated calls for any findings."""

from __future__ import annotations

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
def test_double_apply_is_idempotent(findings) -> None:
    repo = Repo(name="r", path=Path("/tmp"), language="python", github_slug="o/r")

    with patch("consistency_check.filer.subprocess.run") as mock:
        file_repo_findings(repo, findings, apply=False)
        file_repo_findings(repo, findings, apply=False)

    assert mock.call_count == 0
