"""Tests for docs rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.rules import docs
from consistency_check.rules.docs import RULES
from consistency_check.types import Repo

from tests.rules.verdict import verdict

if TYPE_CHECKING:
    from pathlib import Path


def _check(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    return verdict(next(r for r in RULES if r.id == rule_id), repo)


def test_mcp_007_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-007") is None


def test_mcp_007_fail_on_bad_python(bad_python_repo: Path) -> None:
    assert _check(bad_python_repo, "python", "MCP-007") is not None


def test_mcp_009_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-009") is None


def test_mcp_009_fail_when_claude_md_lacks_link(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("nothing useful\n", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    rule = next(r for r in RULES if r.id == "MCP-009")
    assert rule.check(repo) is not None


def test_mcp_027_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-027") is None


def test_mcp_027_fail_on_bad_python(bad_python_repo: Path) -> None:
    evidence = _check(bad_python_repo, "python", "MCP-027")
    assert evidence is not None
    assert "README.md:3" in evidence


def test_mcp_027_fail_on_bad_go(bad_go_repo: Path) -> None:
    assert _check(bad_go_repo, "go", "MCP-027") is not None


def test_mcp_027_scans_docs_markdown(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "design.md").write_text("The client boasts a fast cache.\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is not None


def test_mcp_027_ignores_non_prose_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("a rich tapestry\n", encoding="utf-8")
    (tmp_path / "server.py").write_text("# leverage\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is None


def test_mcp_027_ignores_fenced_code_blocks(tmp_path: Path) -> None:
    # A README's usage examples are code, not prose.
    (tmp_path / "README.md").write_text(
        "# server\n\n```bash\nleverage --tapestry\n```\n\nPlain prose.\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "MCP-027") is None


def test_mcp_027_still_scans_prose_after_a_fence(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# server\n\n```bash\nrun me\n```\n\nWe leverage this.\n", encoding="utf-8"
    )
    evidence = _check(tmp_path, "python", "MCP-027")
    assert evidence is not None
    assert "README.md:7" in evidence


def test_mcp_027_permits_em_dashes_and_curly_quotes(tmp_path: Path) -> None:
    # Typographic patterns are deliberately not part of the vendored list: the
    # standards docs in this suite use em dashes as their established voice.
    (tmp_path / "README.md").write_text("A server — a good one — “quoted”.\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is None


def test_mcp_027_errors_when_pattern_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(docs, "_BANNED_PHRASES", tmp_path / "absent" / "banned-phrases.txt")
    (tmp_path / "README.md").write_text("clean prose\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="banned-phrase list"):
        _check(tmp_path, "python", "MCP-027")


def test_mcp_027_errors_on_an_uncompilable_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_list = tmp_path / "banned-phrases.txt"
    bad_list.write_text("leverage\n(unclosed\n", encoding="utf-8")
    monkeypatch.setattr(docs, "_BANNED_PHRASES", bad_list)
    (tmp_path / "README.md").write_text("clean prose\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid pattern"):
        _check(tmp_path, "python", "MCP-027")


def test_mcp_027_vendored_list_compiles(tmp_path: Path) -> None:
    # The shipped list is the rule's source of truth; a bad edit must not reach
    # users as a regex error at audit time.
    (tmp_path / "README.md").write_text("clean prose\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is None


def test_mcp_027_caps_evidence_with_more_tail(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("leverage\n" * 8, encoding="utf-8")
    evidence = _check(tmp_path, "python", "MCP-027")
    assert evidence is not None
    assert evidence.endswith("and 3 more")


def test_mcp_027_permits_your_tool(tmp_path: Path) -> None:
    # "our tool" is the marketing cliche; "your tool" addressing the reader is
    # ordinary docs prose and must not trip the rule.
    (tmp_path / "README.md").write_text("Point your tool at the socket.\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is None


def test_mcp_027_still_flags_our_tool(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("our tool does the rest.\n", encoding="utf-8")
    assert _check(tmp_path, "python", "MCP-027") is not None
