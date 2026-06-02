"""Tests for CI rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.ci import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language=lang, github_slug="x/y"),
    )


def test_mcp_014_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-014") is None


def test_mcp_017_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-017") is None


def test_mcp_017_fail_on_unpinned_action(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace(
            "actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7",
            "actions/checkout@v4",
        ),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-017") is not None


def test_mcp_025_pass_on_coverage_floor(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-025") is None


def test_mcp_025_fail_without_coverage_floor(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace(" --cov=good_python --cov-fail-under=90", ""), encoding="utf-8"
    )
    assert _check(good_python_repo, "python", "MCP-025") is not None


def test_mcp_025_pass_on_go_coverage_gate(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-025") is None


def test_mcp_025_fail_on_bare_coverprofile(good_go_repo: Path) -> None:
    # A coverprofile report with no threshold gate must not clear MCP-025.
    ci = good_go_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace("go-test-coverage --config .testcoverage.yml", "true"),
        encoding="utf-8",
    )
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_026_pass_on_vuln_scan(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-026") is None


def test_mcp_026_pass_on_safety_check_run_step(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace("- run: uv run pip-audit", "- run: uv run safety check"),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-026") is None


def test_mcp_026_fail_when_safety_check_only_in_comment(good_python_repo: Path) -> None:
    # Prose mentioning a safety check is not a scan; only a run: command counts.
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace("- run: uv run pip-audit", "# TODO: improve safety check here"),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-026") is not None


def test_mcp_026_fail_when_safety_check_commented_in_block_scalar(good_python_repo: Path) -> None:
    # A shell comment inside a ``run: |`` block scalar is not a scan either.
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    block = "- run: |\n          echo build\n          # safety check here"
    ci.write_text(
        ci.read_text().replace("- run: uv run pip-audit", block),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-026") is not None


def test_mcp_026_fail_without_vuln_scan(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(ci.read_text().replace("- run: uv run pip-audit\n", ""), encoding="utf-8")
    assert _check(good_python_repo, "python", "MCP-026") is not None
