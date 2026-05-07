"""Rules: tests (MCP-011, 012, 013)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo


def _check_tests_dir(repo: Repo) -> str | None:
    if repo.language == "go":
        if any(repo.path.rglob("*_test.go")):
            return None
        return "no Go test files (*_test.go) found"
    tests = repo.path / "tests"
    if not tests.is_dir() or not any(tests.rglob("test_*.py")):
        return "tests/ directory missing or empty"
    return None


def _check_unit_integration_split(repo: Repo) -> str | None:
    if repo.language == "go":
        has_top_integration = (repo.path / "integration").is_dir()
        has_build_tags = any(
            "//go:build integration" in p.read_text(encoding="utf-8", errors="replace")
            for p in repo.path.rglob("*_test.go")
        )
        if has_top_integration or has_build_tags:
            return None
        return "no integration/ directory and no //go:build integration tags"
    tests = repo.path / "tests"
    if not (tests / "unit").is_dir():
        return "tests/unit/ missing"
    if not (tests / "integration").is_dir():
        return "tests/integration/ missing"
    return None


def _check_property_tests(repo: Repo) -> str | None:
    if repo.language == "go":
        if any(
            "func Fuzz" in p.read_text(encoding="utf-8", errors="replace")
            for p in repo.path.rglob("*_test.go")
        ):
            return None
        return "no Go fuzz tests (func Fuzz*) found"
    prop_dir = repo.path / "tests" / "property"
    if prop_dir.is_dir() and any(
        "from hypothesis" in p.read_text(encoding="utf-8", errors="replace")
        for p in prop_dir.rglob("test_*.py")
    ):
        return None
    return "no tests/property/ with hypothesis-based tests"


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-011",
        tier=Tier.MUST,
        statement="tests/ directory present",
        check=_check_tests_dir,
    ),
    Rule(
        id="MCP-012",
        tier=Tier.SHOULD,
        statement="Tests separated into unit/ and integration/",
        check=_check_unit_integration_split,
    ),
    Rule(
        id="MCP-013",
        tier=Tier.SHOULD,
        statement="At least one property/fuzz test",
        check=_check_property_tests,
    ),
)
