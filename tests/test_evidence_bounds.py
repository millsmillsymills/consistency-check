"""Per-item bounds on evidence read out of an audited repo and filed publicly."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.filer import _fit_body
from consistency_check.report import render_child_issue
from consistency_check.rules.mcp_protocol import RULES as PROTO_RULES
from consistency_check.rules.mcp_protocol import _go_tool_names
from consistency_check.sources import code_only
from consistency_check.types import Finding, FindingStatus, Repo, Tier

if TYPE_CHECKING:
    from pathlib import Path

_LEAK = (
    "postgres://admin:hunter2@db.corp.internal:5432/prod "
    "AWS_SECRET=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY @someone see #12"
)


def _repo_with_tool(root: Path, name: str) -> Repo:
    """A minimal Python repo whose one tool registers under ``name``."""
    src = root / "src" / root.name.replace("-", "_")
    src.mkdir(parents=True)
    (src / "server.py").write_text(
        f'from mcp.server.fastmcp import FastMCP\n\nmcp = FastMCP("t")\n\n\n'
        f'@mcp.tool(name="{name}")\ndef handler() -> str:\n    return "x"\n',
        encoding="utf-8",
    )
    return Repo(name=root.name, path=root, language="python", github_slug="x/y")


def _evidence(repo: Repo, rule_id: str) -> str | None:
    result = next(r for r in PROTO_RULES if r.id == rule_id).check(repo)
    return result if isinstance(result, str) else None


@pytest.mark.parametrize("rule_id", ["PROTO-001", "PROTO-002", "PROTO-018"])
def test_an_offending_tool_name_is_never_published(tmp_path: Path, rule_id: str) -> None:
    """A registered name is an arbitrary literal; truncating it still publishes its front."""
    repo = _repo_with_tool(tmp_path / "demo-mcp", _LEAK + "x" * 200)

    evidence = _evidence(repo, rule_id)

    assert evidence is not None
    assert "hunter2" not in evidence
    assert "db.corp.internal" not in evidence
    assert "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY" not in evidence
    assert "@someone" not in evidence
    # The declaring symbol is what a reader needs, and it is bounded.
    assert "handler" in evidence


def test_the_filed_child_issue_carries_no_part_of_the_name(tmp_path: Path) -> None:
    evidence = _evidence(_repo_with_tool(tmp_path / "demo-mcp", _LEAK), "PROTO-001")
    assert evidence is not None
    finding = Finding(
        rule_id="PROTO-001", tier=Tier.MUST, status=FindingStatus.FAIL, evidence=evidence
    )

    body = render_child_issue("t", finding)

    assert body is not None
    assert "hunter2" not in body
    assert "@someone" not in body


def test_a_tool_registered_through_a_helper_is_still_graded() -> None:
    """Excluding "(" from the WithTools window passed a bad name on this shape."""
    assert _go_tool_names('s.WithTools(ToolFor("Bad-Name"))\n') == ["Bad-Name"]


def test_a_withtools_call_with_no_literal_grades_nothing() -> None:
    """The window must not walk out of the call and grade the next quoted span."""
    assert _go_tool_names('s.WithTools(tools...)\nconst other = "unrelated"\n') == []


def test_an_escaped_newline_does_not_leak_the_next_line_into_code() -> None:
    """A backslash must not step over the newline that ends an interpreted string."""
    go = 'package t\na := "abc\\\nsecret := "TOKEN"\nos.Stdout.Write(x)\n'

    stripped = code_only(go, "//")

    assert "TOKEN" not in stripped
    assert "os.Stdout.Write" in stripped


def test_an_oversized_body_is_cut_on_a_line_boundary() -> None:
    """A mid-span cut drops a closing backtick and unfences whatever follows."""
    line = "- **X-001** — `@someone see #12`\n"
    body = line * 4000

    fitted = _fit_body(body)

    assert len(fitted) <= 65_000
    assert fitted.count("`") % 2 == 0
