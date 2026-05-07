"""Tests for structure rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.structure import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _run(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    rule = next(r for r in RULES if r.id == rule_id)
    return rule.check(repo)


def test_mcp_001_pass_on_good_python(good_python_repo: Path) -> None:
    assert _run(good_python_repo, "python", "MCP-001") is None


def test_mcp_001_fail_on_bad_python(bad_python_repo: Path) -> None:
    evidence = _run(bad_python_repo, "python", "MCP-001")
    assert evidence is not None
    assert "LICENSE" in evidence or "SECURITY.md" in evidence or "CLAUDE.md" in evidence


def test_mcp_005_pass_on_good_python(good_python_repo: Path) -> None:
    assert _run(good_python_repo, "python", "MCP-005") is None


def test_mcp_005_fail_when_pycache_committed(good_python_repo: Path) -> None:
    (good_python_repo / "src" / "good_python" / "__pycache__").mkdir()
    (good_python_repo / "src" / "good_python" / "__pycache__" / "x.pyc").write_bytes(b"")
    evidence = _run(good_python_repo, "python", "MCP-005")
    assert evidence is not None
    assert "__pycache__" in evidence


def test_mcp_005_skips_artifacts_inside_venv(good_python_repo: Path) -> None:
    venv_pkg = good_python_repo / ".venv" / "lib" / "python3.13" / "site-packages" / "foo"
    venv_pkg.mkdir(parents=True)
    (venv_pkg / "__pycache__").mkdir()
    (venv_pkg / "__pycache__" / "x.pyc").write_bytes(b"")
    assert _run(good_python_repo, "python", "MCP-005") is None


def test_mcp_002_accepts_canonical_apache_text(good_python_repo: Path) -> None:
    license_file = good_python_repo / "LICENSE"
    license_file.write_text(
        "                                 Apache License\n"
        "                           Version 2.0, January 2004\n"
        "                        http://www.apache.org/licenses/\n",
        encoding="utf-8",
    )
    assert _run(good_python_repo, "python", "MCP-002") is None


def test_mcp_002_fails_when_license_text_does_not_match_spdx(good_python_repo: Path) -> None:
    license_file = good_python_repo / "LICENSE"
    license_file.write_text("MIT License\n\nPermission is hereby granted...\n", encoding="utf-8")
    evidence = _run(good_python_repo, "python", "MCP-002")
    assert evidence is not None
    assert "Apache-2.0" in evidence
