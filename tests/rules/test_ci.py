"""Tests for CI rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.ci import RULES
from consistency_check.types import Repo, Tier

from tests.rules.verdict import verdict

if TYPE_CHECKING:
    from pathlib import Path


_BY_ID = {r.id: r for r in RULES}


def _repo(p: Path) -> Repo:
    return Repo(name="x", path=p, language="python", github_slug="x/y")


def _check(p: Path, lang: str, rid: str) -> str | None:
    return verdict(
        next(r for r in RULES if r.id == rid),
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


def test_mcp_025_pass_on_make_coverage_check_gate(good_go_repo: Path) -> None:
    # A project `make coverage-check` target (a script that exits non-zero below
    # a floor) is a real gate, even without go-test-coverage.
    ci = good_go_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace(
            "go-test-coverage --config .testcoverage.yml", "make coverage-check"
        ),
        encoding="utf-8",
    )
    assert _check(good_go_repo, "go", "MCP-025") is None


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


def test_mcp_026_fail_when_safety_check_in_trailing_inline_comment(good_python_repo: Path) -> None:
    # `run: echo hi  # safety check` — the text after ` #` is a comment, not a scan.
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace("- run: uv run pip-audit", "- run: echo hi  # safety check here"),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-026") is not None


def test_mcp_026_pass_when_safety_check_precedes_trailing_comment(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace("- run: uv run pip-audit", "- run: uv run safety check  # audit"),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "python", "MCP-026") is None


def test_mcp_026_fail_without_vuln_scan(good_python_repo: Path) -> None:
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(ci.read_text().replace("- run: uv run pip-audit\n", ""), encoding="utf-8")
    assert _check(good_python_repo, "python", "MCP-026") is not None


def test_mcp_018_fails_without_publish_step(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "release.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - run: echo built\n", encoding="utf-8"
    )
    evidence = verdict(_BY_ID["MCP-018"], _repo(tmp_path))
    assert evidence is not None
    assert "artifact" in evidence


def test_mcp_018_passes_with_image_push(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "release.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - uses: docker/build-push-action@abc\n", encoding="utf-8"
    )
    assert verdict(_BY_ID["MCP-018"], _repo(tmp_path)) is None


def test_mcp_018_fails_when_workflow_missing(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert verdict(_BY_ID["MCP-018"], _repo(tmp_path)) is not None


def test_mcp_018_contributing_fallback_removed(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CONTRIBUTING.md").write_text("## Release\nTag and push.\n", encoding="utf-8")
    assert verdict(_BY_ID["MCP-018"], _repo(tmp_path)) is not None


def test_mcp_018_is_must_tier() -> None:
    assert _BY_ID["MCP-018"].tier is Tier.MUST


def _replace_ci_step(repo: Path, old: str, new: str) -> None:
    ci = repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(ci.read_text().replace(old, new), encoding="utf-8")


def test_mcp_025_pass_on_gate_inside_make_recipe(good_go_repo: Path) -> None:
    # The gate token lives in the Makefile recipe, not the workflow YAML.
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make cover")
    (good_go_repo / "Makefile").write_text(
        "build:\n\tgo build ./...\n\ncover:\n\tgo-test-coverage --config .testcoverage.yml\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "go", "MCP-025") is None


def test_mcp_025_pass_on_gate_inside_script_called_by_make(good_go_repo: Path) -> None:
    # workflow -> make target -> shell script, the protonmail-mcp shape.
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make cover")
    (good_go_repo / "Makefile").write_text(
        "cover:\n\t./scripts/cover.sh cov.out\n", encoding="utf-8"
    )
    script = good_go_repo / "scripts" / "cover.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\ngo-test-coverage --config x.yml\n", encoding="utf-8")
    assert _check(good_go_repo, "go", "MCP-025") is None


def test_mcp_025_pass_on_gate_inside_script_called_directly(good_python_repo: Path) -> None:
    _replace_ci_step(good_python_repo, "--cov=good_python --cov-fail-under=90", "")
    _replace_ci_step(good_python_repo, "- run: uv run pip-audit", "- run: ./scripts/cov.sh")
    script = good_python_repo / "scripts" / "cov.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("pytest --cov-fail-under=85\n", encoding="utf-8")
    assert _check(good_python_repo, "python", "MCP-025") is None


def test_mcp_025_still_fails_when_recipe_only_reports(good_go_repo: Path) -> None:
    # Following the indirection must not turn a report-only recipe into a gate.
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make cover")
    (good_go_repo / "Makefile").write_text(
        "cover:\n\tgo test ./... -coverprofile=cov.out -covermode=atomic\n", encoding="utf-8"
    )
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_025_ignores_script_path_outside_the_repo(good_go_repo: Path) -> None:
    outside = good_go_repo.parent / "escape.sh"
    outside.write_text("go-test-coverage --config x.yml\n", encoding="utf-8")
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "../escape.sh")
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_025_unknown_make_target_is_not_a_gate(good_go_repo: Path) -> None:
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make absent")
    (good_go_repo / "Makefile").write_text("cover:\n\tgo-test-coverage\n", encoding="utf-8")
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_025_ignores_gate_token_in_a_recipe_comment(good_go_repo: Path) -> None:
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make cover")
    (good_go_repo / "Makefile").write_text(
        "cover:\n\t# TODO: wire up go-test-coverage here\n\tgo test ./...\n", encoding="utf-8"
    )
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_025_ignores_gate_token_in_a_script_comment(good_go_repo: Path) -> None:
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "./cover.sh")
    (good_go_repo / "cover.sh").write_text(
        "#!/usr/bin/env bash\n# we should add go-test-coverage one day\ngo test ./...\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "go", "MCP-025") is not None


def test_mcp_025_follows_make_prerequisites(good_go_repo: Path) -> None:
    # ``make ci`` aggregating a coverage target is as common as calling it directly.
    _replace_ci_step(good_go_repo, "go-test-coverage --config .testcoverage.yml", "make ci")
    (good_go_repo / "Makefile").write_text(
        "ci: lint cover\n\ncover:\n\tgo-test-coverage --config x.yml\n", encoding="utf-8"
    )
    assert _check(good_go_repo, "go", "MCP-025") is None


def test_mcp_026_ignores_scanner_named_in_a_script(good_go_repo: Path) -> None:
    # MCP-026 is a MUST and stays on the workflow corpus: a scanner reachable
    # only through an unrelated script must not clear it.
    ci = good_go_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(ci.read_text().replace("govulncheck ./...", "./bootstrap.sh"), encoding="utf-8")
    (good_go_repo / "bootstrap.sh").write_text("govulncheck ./...\n", encoding="utf-8")
    assert _check(good_go_repo, "go", "MCP-026") is not None


def test_mcp_017_names_the_workflow_not_the_uses_line(good_python_repo: Path) -> None:
    # The matched `uses:` line carries the audited repo's org and any private
    # composite action it depends on, and this evidence is filed publicly.
    ci = good_python_repo / ".github" / "workflows" / "ci.yml"
    ci.write_text(
        ci.read_text().replace(
            "actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7",
            "internal-org/private-build-action@v4",
        ),
        encoding="utf-8",
    )
    evidence = _check(good_python_repo, "python", "MCP-017")
    assert evidence is not None
    assert "ci.yml" in evidence
    assert "internal-org" not in evidence
    assert "private-build-action" not in evidence
