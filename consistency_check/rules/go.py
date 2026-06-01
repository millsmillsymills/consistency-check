"""Rules: Go (GO-001..015)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

_GOLANGCI_REQUIRED = ("errcheck", "govet", "staticcheck", "unused", "gocritic")
_GO_ONLY = frozenset({"go"})
_SKIP_DIRS = frozenset({"vendor", "node_modules"})

# Matches a real `go` statement on a source line: the `go` keyword at a point
# where a statement can begin (line start, or after `{`/`;`), then a function
# literal, identifier call, method call, or composite-literal construction.
# Allowing `{`/`;` catches inline forms like `if cond { go run() }`; the
# statement-boundary requirement still skips `//` comments and prose mentions
# of "go through", "go.sum", etc.
_GOROUTINE_RE = re.compile(
    r"(?:^|[{;])\s*go\s+(func\b|\w+(\.\w+)*\(|&?\w+\{)",
    re.MULTILINE,
)

# Matches the common Go table-driven test idioms where the table is an inline
# struct (or pointer-to-struct) literal. The variable name is unconstrained
# (people use `tests`, `tt`, `tc`, `tcs`, `cases`, `table`, `examples`, etc.);
# what matters is that there's a slice or map of structs declared or ranged
# over. The split declaration/range form is handled separately below.
_TABLE_DRIVEN_RE = re.compile(
    r"\w+\s*:=\s*\[\]\*?struct\s*\{"
    r"|\w+\s*:=\s*map\[\s*\w+\s*\]\s*\*?struct\s*\{"
    r"|for\s+[\w,\s]+:=\s*range\s*\[\]\*?struct\s*\{",
)

# A struct table bound to a variable, capturing the variable name (group 1) and,
# when the element is a named type rather than an anonymous struct, that type
# name (group 2). Covers `:=`/`=`/`var x =`, slice/array/map containers, and
# pointer elements. Used to detect the split form where the table is declared on
# one line and ranged on another.
_TABLE_DECL_RE = re.compile(
    r"\b(\w+)\s*(?::=|=)\s*"
    r"(?:\[\d*\]|map\[\s*\w+\s*\])\*?"
    r"(?:struct\s*\{|(\w+)\s*\{)",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _skipped(p: Path, root: Path) -> bool:
    try:
        rel_parts = p.relative_to(root).parts
    except ValueError:
        return True
    # Skip dot-prefixed dirs (.git, .claude/worktrees, .venv, ...) so stale
    # repo copies under agent worktrees or caches don't poison the heuristics.
    return any(part.startswith(".") or part in _SKIP_DIRS for part in rel_parts)


def _check_layout(repo: Repo) -> str | None:
    if not (repo.path / "cmd").is_dir():
        return "cmd/ missing"
    if not (repo.path / "internal").is_dir():
        return "internal/ missing"
    if not any((repo.path / "cmd").rglob("main.go")):
        return "no cmd/<binary>/main.go found"
    return None


def _check_go_version(repo: Repo) -> str | None:
    text = _read(repo.path / "go.mod")
    m = re.search(r"^go\s+(\d+)\.(\d+)", text, re.MULTILINE)
    if m is None:
        return "go.mod missing 'go' directive"
    major, minor = int(m.group(1)), int(m.group(2))
    if (major, minor) < (1, 22):
        return f"go {major}.{minor}; require >= 1.22"
    return None


def _check_go_sum(repo: Repo) -> str | None:
    return None if (repo.path / "go.sum").is_file() else "go.sum missing"


def _check_golangci(repo: Repo) -> str | None:
    cfg = repo.path / ".golangci.yml"
    if not cfg.is_file():
        return ".golangci.yml missing"
    text = _read(cfg)
    missing = [n for n in _GOLANGCI_REQUIRED if n not in text]
    return f"golangci-lint missing linters: {missing}" if missing else None


def _check_gofmt_in_ci(repo: Repo) -> str | None:
    text = _read(repo.path / ".github" / "workflows" / "ci.yml")
    if "gofmt" in text or "goimports" in text:
        return None
    return "ci.yml does not invoke gofmt/goimports"


def _is_table_driven(text: str) -> bool:
    if _TABLE_DRIVEN_RE.search(text):
        return True
    # Split form: a struct table bound to a variable on one line and ranged on
    # another. A named-type element only counts if that type is a struct defined
    # in the same file, so `[]string{...}` and friends don't read as a table.
    struct_types = set(re.findall(r"\btype\s+(\w+)\s+struct\b", text))
    for m in _TABLE_DECL_RE.finditer(text):
        ident, elem_type = m.group(1), m.group(2)
        if elem_type is not None and elem_type not in struct_types:
            continue
        if re.search(rf"\brange\s+{re.escape(ident)}\b", text):
            return True
    return False


def _check_table_driven(repo: Repo) -> str | None:
    # Fuzz and property-based tests use their own input-generation paradigm
    # and are not natural table-driven candidates; excluding them keeps the
    # signal focused on unit + integration tests where the pattern applies.
    test_files = [
        p
        for p in repo.path.rglob("*_test.go")
        if not _skipped(p, repo.path)
        and not (p.name == "fuzz_test.go" or p.name.endswith("_fuzz_test.go"))
        and not (p.name == "property_test.go" or p.name.endswith("_property_test.go"))
    ]
    if not test_files:
        return "no *_test.go found"
    table_driven = sum(1 for p in test_files if _is_table_driven(_read(p)))
    if table_driven * 2 < len(test_files):
        return f"only {table_driven}/{len(test_files)} test files use table-driven pattern"
    return None


def _check_race_in_ci(repo: Repo) -> str | None:
    text = _read(repo.path / ".github" / "workflows" / "ci.yml")
    return None if "-race" in text else "go test -race not present in ci.yml"


def _check_integration_split(repo: Repo) -> str | None:
    if (repo.path / "integration").is_dir():
        return None
    for p in repo.path.rglob("*_test.go"):
        if _skipped(p, repo.path):
            continue
        if "//go:build integration" in _read(p):
            return None
    return "no integration/ directory and no //go:build integration tags"


def _check_error_wrapping(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in repo.path.rglob("*.go"):
        if p.name.endswith("_test.go") or _skipped(p, repo.path):
            continue
        text = _read(p)
        for _ in re.finditer(r"return\s+(\w+),?\s*err\s*$", text, re.MULTILINE):
            if "fmt.Errorf" not in text or "%w" not in text:
                bad.append(p.relative_to(repo.path).as_posix())
                break
    return f"functions returning unwrapped errors (heuristic): {bad[:5]}" if bad else None


def _ctx_first(params: str) -> bool:
    if not params.strip():
        return False
    first = params.split(",", maxsplit=1)[0].strip()
    return "context.Context" in first


def _check_context_first(repo: Repo) -> str | None:
    bad: list[str] = []
    internal = repo.path / "internal"
    if not internal.is_dir():
        return None
    for p in internal.rglob("*.go"):
        if p.name.endswith("_test.go"):
            continue
        text = _read(p)
        for m in re.finditer(
            r"func\s+(?:\([^)]+\)\s+)?"
            r"([A-Z]\w*?(?:Get|List|Create|Update|Delete|Send|Fetch)\w*)\s*\(([^)]*)\)",
            text,
        ):
            if not _ctx_first(m.group(2)):
                bad.append(f"{p.name}::{m.group(1)}")  # noqa: PERF401
    return f"funcs missing context.Context first: {bad[:5]}" if bad else None


def _check_init_simple(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in repo.path.rglob("*.go"):
        if p.name.endswith("_test.go") or _skipped(p, repo.path):
            continue
        text = _read(p)
        for m in re.finditer(r"func\s+init\s*\(\)\s*\{([^}]*)\}", text, re.DOTALL):
            body = m.group(1).strip()
            stmts = [s for s in body.split("\n") if s.strip() and not s.strip().startswith("//")]
            if len(stmts) > 3:
                bad.append(p.relative_to(repo.path).as_posix())
    return f"non-trivial init() functions: {bad[:3]}" if bad else None


def _check_mcp_go(repo: Repo) -> str | None:
    # Either the original community SDK (mark3labs/mcp-go) or the official
    # upstream SDK (modelcontextprotocol/go-sdk) satisfies the rule. The
    # official SDK shipped after this rule was first authored and is the
    # preferred choice for new servers; both are acceptable.
    text = _read(repo.path / "go.mod")
    if "mark3labs/mcp-go" in text or "modelcontextprotocol/go-sdk" in text:
        return None
    return "go.mod missing github.com/mark3labs/mcp-go or github.com/modelcontextprotocol/go-sdk"


def _check_errgroup(repo: Repo) -> str | None:
    has_goroutine = any(
        _GOROUTINE_RE.search(_read(p))
        for p in repo.path.rglob("*.go")
        if not p.name.endswith("_test.go") and not _skipped(p, repo.path)
    )
    if not has_goroutine:
        return None
    has_errgroup = any(
        "errgroup" in _read(p) for p in repo.path.rglob("*.go") if not _skipped(p, repo.path)
    )
    return None if has_errgroup else "uses goroutines but no errgroup imported"


def _check_no_panic(repo: Repo) -> str | None:
    bad: list[str] = []
    internal = repo.path / "internal"
    if not internal.is_dir():
        return None
    for p in internal.rglob("*.go"):
        if p.name.endswith("_test.go"):
            continue
        text = _read(p)
        if re.search(r"\bpanic\(", text):
            bad.append(p.relative_to(repo.path).as_posix())
    return f"panic() in library code: {bad[:3]}" if bad else None


def _check_log_lib(repo: Repo) -> str | None:
    sources = [p for p in repo.path.rglob("*.go") if not _skipped(p, repo.path)]
    has_slog = any("log/slog" in _read(p) for p in sources)
    has_zerolog = any('"github.com/rs/zerolog' in _read(p) for p in sources)
    if has_slog or has_zerolog:
        return None
    return "no slog or zerolog imported"


RULES: tuple[Rule, ...] = (
    Rule(
        id="GO-001",
        tier=Tier.MUST,
        statement="Layout cmd/ + internal/",
        check=_check_layout,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-002",
        tier=Tier.MUST,
        statement="go.mod >= 1.22",
        check=_check_go_version,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-003",
        tier=Tier.MUST,
        statement="go.sum committed",
        check=_check_go_sum,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-004",
        tier=Tier.MUST,
        statement="golangci-lint configured",
        check=_check_golangci,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-005",
        tier=Tier.MUST,
        statement="gofmt/goimports enforced via CI",
        check=_check_gofmt_in_ci,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-006",
        tier=Tier.SHOULD,
        statement="Tests use table-driven pattern",
        check=_check_table_driven,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-007",
        tier=Tier.MUST,
        statement="go test -race in CI",
        check=_check_race_in_ci,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-008",
        tier=Tier.SHOULD,
        statement="Integration tests in separate dir or build tag",
        check=_check_integration_split,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-009",
        tier=Tier.MUST,
        statement="Errors wrapped with %w",
        check=_check_error_wrapping,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-010",
        tier=Tier.MUST,
        statement="context.Context first param of API funcs",
        check=_check_context_first,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-011",
        tier=Tier.MUST,
        statement="No init() with non-trivial logic",
        check=_check_init_simple,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-012",
        tier=Tier.MUST,
        statement="Use a maintained MCP Go SDK (mark3labs/mcp-go or modelcontextprotocol/go-sdk)",
        check=_check_mcp_go,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-013",
        tier=Tier.SHOULD,
        statement="errgroup for parallel work",
        check=_check_errgroup,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-014",
        tier=Tier.MUST,
        statement="No panic in library packages",
        check=_check_no_panic,
        applies_to=_GO_ONLY,
    ),
    Rule(
        id="GO-015",
        tier=Tier.SHOULD,
        statement="Logging via slog or zerolog",
        check=_check_log_lib,
        applies_to=_GO_ONLY,
    ),
)
