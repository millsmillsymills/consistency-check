"""Tests for GO-* rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.go import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="go", github_slug="x/y"),
    )


def test_go_001_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-001") is None


def test_go_004_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-004") is None


def test_go_004_fail_when_no_golangci(good_go_repo: Path) -> None:
    (good_go_repo / ".golangci.yml").unlink()
    assert _check(good_go_repo, "GO-004") is not None


def test_go_012_pass(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-012") is None


def test_go_012_pass_with_official_sdk(good_go_repo: Path) -> None:
    (good_go_repo / "go.mod").write_text(
        "module foo\ngo 1.22\nrequire github.com/modelcontextprotocol/go-sdk v1.0.0\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-012") is None


def test_go_012_fail_when_mcp_go_missing(good_go_repo: Path) -> None:
    (good_go_repo / "go.mod").write_text("module foo\ngo 1.22\n", encoding="utf-8")
    assert _check(good_go_repo, "GO-012") is not None


def test_go_013_pass_when_no_goroutines(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "GO-013") is None


def test_go_013_pass_when_only_comment_mentions_go(good_go_repo: Path) -> None:
    # Comments referencing "go" (e.g. "go through", "go.sum", "go run") must
    # not trigger the heuristic — only real `go <expr>` statements do.
    (good_go_repo / "internal" / "tools" / "doc.go").write_text(
        "package tools\n\n"
        "// All authentication mutations go through here. See go.sum for hashes.\n"
        "// Invoke as `go run ./cmd/foo`.\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-013") is None


def test_go_013_fail_when_goroutine_without_errgroup(good_go_repo: Path) -> None:
    (good_go_repo / "internal" / "worker" / "worker.go").parent.mkdir(parents=True)
    (good_go_repo / "internal" / "worker" / "worker.go").write_text(
        "package worker\n\nfunc Start() {\n\tgo func() { _ = 1 }()\n}\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-013") is not None


def test_go_013_fail_when_inline_goroutine(good_go_repo: Path) -> None:
    # A goroutine launched mid-line (after `{`) must still be detected.
    (good_go_repo / "internal" / "worker" / "worker.go").parent.mkdir(parents=True)
    (good_go_repo / "internal" / "worker" / "worker.go").write_text(
        "package worker\n\nfunc Start(cond bool) {\n\tif cond { go run() }\n}\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-013") is not None


def test_go_006_excludes_fuzz_and_property_tests(good_go_repo: Path) -> None:
    # Fuzz / property tests should not drag down the table-driven percentage.
    (good_go_repo / "internal" / "tools" / "x_fuzz_test.go").write_text(
        'package tools\nimport "testing"\nfunc FuzzX(f *testing.F) {}\n',
        encoding="utf-8",
    )
    (good_go_repo / "internal" / "tools" / "x_property_test.go").write_text(
        'package tools\nimport "testing"\nfunc TestXProperty(t *testing.T) {}\n',
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-006") is None


def test_go_006_pass_with_cases_variable_name(good_go_repo: Path) -> None:
    # `cases := []struct{...}` is just as table-driven as `tests := ...` —
    # the variable name is incidental.
    for i in range(3):
        (good_go_repo / "internal" / "tools" / f"more_{i}_test.go").write_text(
            'package tools\nimport "testing"\n'
            "func TestX(t *testing.T) {\n"
            '\tcases := []struct{ name string }{{"a"}, {"b"}}\n'
            "\tfor _, tc := range cases { t.Run(tc.name, func(t *testing.T) {}) }\n"
            "}\n",
            encoding="utf-8",
        )
    assert _check(good_go_repo, "GO-006") is None


def test_go_006_pass_with_map_table(good_go_repo: Path) -> None:
    for i in range(3):
        (good_go_repo / "internal" / "tools" / f"map_{i}_test.go").write_text(
            'package tools\nimport "testing"\n'
            "func TestX(t *testing.T) {\n"
            '\ttests := map[string]struct{ in int }{"a": {1}}\n'
            "\tfor name, tc := range tests {\n"
            "\t\tt.Run(name, func(t *testing.T) { _ = tc.in })\n"
            "\t}\n"
            "}\n",
            encoding="utf-8",
        )
    assert _check(good_go_repo, "GO-006") is None


def test_go_013_pass_when_goroutine_with_errgroup(good_go_repo: Path) -> None:
    (good_go_repo / "internal" / "worker" / "worker.go").parent.mkdir(parents=True)
    (good_go_repo / "internal" / "worker" / "worker.go").write_text(
        "package worker\n\n"
        'import "golang.org/x/sync/errgroup"\n\n'
        "func Start() {\n"
        "\tvar g errgroup.Group\n"
        "\tg.Go(func() error { return nil })\n"
        "\t_ = g.Wait()\n"
        "}\n",
        encoding="utf-8",
    )
    assert _check(good_go_repo, "GO-013") is None
