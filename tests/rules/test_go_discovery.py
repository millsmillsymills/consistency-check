"""Go ownership boundaries must agree across rule families."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.rules.go import RULES as GO_RULES
from consistency_check.rules.mcp_protocol import RULES as PROTO_RULES
from consistency_check.rules.tests import RULES as TEST_RULES
from consistency_check.types import Repo

from tests.rules.verdict import verdict

if TYPE_CHECKING:
    from pathlib import Path

_EXCLUDED = ["vendor", "third_party", "testdata", "node_modules", ".worktrees", ".cache"]


@pytest.mark.parametrize("excluded", _EXCLUDED)
def test_excluded_production_cannot_introduce_rule_failures(
    good_go_repo: Path, excluded: str
) -> None:
    source = good_go_repo / "internal" / excluded / "poison.go"
    source.parent.mkdir(parents=True)
    source.write_text(
        "package poison\n"
        "func GetBad() { panic(1) }\n"
        "func start() { go run() }\n"
        "func init() {\n a()\n b()\n c()\n d()\n}\n"
        "func get() (int, error) {\n return 0, err\n}\n"
        "const retired = -32002\n",
        encoding="utf-8",
    )
    repo = Repo(name="good", path=good_go_repo, language="go", github_slug="x/y")
    checked = {"GO-009", "GO-010", "GO-011", "GO-013", "GO-014", "PROTO-026"}
    results = {r.id: verdict(r, repo) for r in (*GO_RULES, *PROTO_RULES) if r.id in checked}
    assert results == dict.fromkeys(checked)


@pytest.mark.parametrize("excluded", _EXCLUDED)
def test_excluded_sources_cannot_satisfy_repository_requirements(
    tmp_path: Path, excluded: str
) -> None:
    dependency = tmp_path / "cmd" / excluded
    dependency.mkdir(parents=True)
    (tmp_path / "internal").mkdir()
    (dependency / "main.go").write_text('package main\nimport "log/slog"\n', encoding="utf-8")
    (dependency / "main_test.go").write_text(
        "//go:build integration\npackage main\n"
        "func FuzzX(f *testing.F) {}\n"
        "func TestX(t *testing.T) { tests := []struct{}{}; for range tests {} }\n",
        encoding="utf-8",
    )
    repo = Repo(name="x", path=tmp_path, language="go", github_slug="x/y")
    checked = {"GO-001", "GO-006", "GO-008", "GO-015", "MCP-011", "MCP-012", "MCP-013", "PROTO-008"}
    results = {
        r.id: verdict(r, repo) for r in (*GO_RULES, *PROTO_RULES, *TEST_RULES) if r.id in checked
    }
    assert set(results) == checked
    assert all(isinstance(evidence, str) for evidence in results.values()), results


def test_owned_internal_code_is_still_graded(tmp_path: Path) -> None:
    source = tmp_path / "internal" / "owned" / "main.go"
    source.parent.mkdir(parents=True)
    source.write_text("package owned\nfunc GetBad() { panic(1) }\n", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="go", github_slug="x/y")
    for rule in GO_RULES:
        if rule.id in {"GO-010", "GO-014"}:
            assert verdict(rule, repo) is not None, rule.id


def test_test_only_logger_cannot_satisfy_production_logging(tmp_path: Path) -> None:
    (tmp_path / "main_test.go").write_text('package main\nimport "log/slog"\n', encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="go", github_slug="x/y")
    assert verdict(next(r for r in GO_RULES if r.id == "GO-015"), repo) is not None
