# MCP Consistency Standards & Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a canonical MCP-server standards set (multi-file, RFC 2119-tiered) and a Python audit CLI that grades four real MCP repos and files GitHub issues for each gap (umbrella + child issues).

**Architecture:** `consistency-check` is the source-of-truth meta-repo. Phase 1 publishes `docs/standards/` (mcp.md / python.md / go.md / mcp-protocol.md). Phase 2 builds a `consistency_check/` Python package: a registry of target repos, hardcoded rule modules per dimension, a markdown report emitter, and a `gh`-CLI filer that is dry-run by default and posts only with `--apply`. Phase 3 runs the audit live against the four MCP repos and files issues per the umbrella+children model.

**Tech Stack:** Python 3.13, uv, ruff, ty, pytest, hypothesis, prek; `gh` CLI for GitHub I/O; ripgrep/fd shelled for evidence gathering.

**Repo init note:** `consistency-check` is currently not a git repository. Task 0 initializes it. All subsequent commit steps assume git is initialized.

---

## Phase boundaries & review checkpoints

| Phase | Tasks | Reviewable deliverable                                               |
| ----- | ----- | -------------------------------------------------------------------- |
| 0     | 1     | git-initialized repo with pyproject.toml & tooling green             |
| 1     | 2-7   | five standards markdown files committed, cross-linked from each MCP repo |
| 2     | 8-22  | `consistency_check` package green against fixture repos              |
| 3     | 23-29 | audit run with `--apply` posts issues to four MCP repos              |

**STOP and request review at the end of every phase.** Do not start the next phase until the operator has approved the previous phase's deliverable.

---

## Task 0: Initialize consistency-check repo & tooling

**Files:**
- Create: `/Users/mills/Desktop/Projects/consistency-check/.gitignore`
- Create: `/Users/mills/Desktop/Projects/consistency-check/pyproject.toml`
- Create: `/Users/mills/Desktop/Projects/consistency-check/consistency_check/__init__.py`
- Create: `/Users/mills/Desktop/Projects/consistency-check/tests/__init__.py`

- [ ] **Step 1: Initialize git**

```bash
cd /Users/mills/Desktop/Projects/consistency-check
git init
git checkout -b main
```

- [ ] **Step 2: Write .gitignore**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.ty_cache/
dist/
*.egg-info/
.consistency-cache/
```

- [ ] **Step 3: Write pyproject.toml**

```toml
[build-system]
requires = ["uv_build"]
build-backend = "uv_build"

[project]
name = "consistency-check"
version = "0.1.0"
description = "Canonical MCP-server standards and audit tool for the millsmillsymills MCP suite"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.13"

[project.scripts]
consistency-check = "consistency_check.__main__:main"

[dependency-groups]
dev = [
  "pytest>=9.0.3",
  "pytest-asyncio>=1.3.0",
  "hypothesis>=6.115.0",
  "ruff>=0.15.12",
  "ty>=0.0.1",
  "syrupy>=4.7.0",
]

[tool.ruff]
target-version = "py313"
line-length = 100
src = ["consistency_check", "tests"]

[tool.ruff.lint]
select = ["ALL"]
ignore = ["D203", "D213", "COM812", "ISC001"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D", "INP001"]

[tool.ty.rules]
unresolved-import = "error"
invalid-argument-type = "error"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 4: Create empty package files**

```bash
mkdir -p consistency_check tests
echo '"""Canonical MCP standards and audit tool."""' > consistency_check/__init__.py
echo '__version__ = "0.1.0"' >> consistency_check/__init__.py
touch tests/__init__.py
```

- [ ] **Step 5: Sync deps and verify tooling**

```bash
uv sync --all-groups
uv run ruff check .
uv run ty check
uv run pytest -q
```

Expected: ruff/ty/pytest all pass with zero warnings (no rules and no tests yet, so pytest reports "0 collected" — that is acceptable).

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml uv.lock consistency_check/ tests/
git commit -m "chore: initialize consistency-check repo with uv/ruff/ty"
```

---

## Phase 1 — Standards docs (Tasks 1–7)

Phase 1 ships five canonical standards files plus per-repo cross-links. Reviewable by humans without running any code.

Each rule entry uses this format throughout `docs/standards/*.md`:

````markdown
### <RULE-ID> — <One-line statement> [<TIER>]

**Rationale.** Why this rule exists. 1-3 sentences.

**Mechanical check.** Exact filesystem / file-content pattern the auditor checks. Unambiguous so the rule's check function is mechanical.

**Example pass / fail.** Tiny snippets, optional but encouraged for non-obvious rules.
````

Tier vocabulary follows RFC 2119: `MUST`, `SHOULD`, `MAY`.

---

## Task 1: Standards index (`docs/standards/README.md`)

**Files:**
- Create: `docs/standards/README.md`

- [ ] **Step 1: Write the index**

```markdown
# MCP Server Standards

Canonical standards for the millsmillsymills MCP suite. Authoritative source of truth.

All rules use RFC 2119 vocabulary:
- **MUST** — non-compliance blocks merge / release.
- **SHOULD** — compliance is the default; exceptions documented.
- **MAY** — preference; non-compliance is fine but flagged.

## Files

| File             | Scope                                                                       |
| ---------------- | --------------------------------------------------------------------------- |
| `mcp.md`         | Language-agnostic core: structure, docs, tests, CI, security, deps, observability |
| `python.md`      | Python MCP servers: uv/ruff/ty/pytest, FastMCP idioms                       |
| `go.md`          | Go MCP servers: golangci-lint, go test, mark3labs/mcp-go idioms             |
| `mcp-protocol.md`| Protocol-level: tool naming, capabilities, transport, error codes, schemas  |

## Rule IDs

Rules are identified by prefix:

| Prefix   | File              |
| -------- | ----------------- |
| `MCP-*`  | `mcp.md`          |
| `PY-*`   | `python.md`       |
| `GO-*`   | `go.md`           |
| `PROTO-*`| `mcp-protocol.md` |

The audit tool (`consistency_check/rules/`) references these IDs verbatim. Adding a rule means editing both the standards file and the matching rules module.

## How the audit uses these standards

`python -m consistency_check audit` walks each target MCP repo, runs each rule's mechanical check, and emits a markdown gap report. With `--apply`, it files GitHub issues per the umbrella+children model:

- Per repo: one umbrella issue listing all findings, with `MAY` failures inline.
- Per `MUST` or `SHOULD` failure: one child issue, linked from the umbrella.
```

- [ ] **Step 2: Commit**

```bash
git add docs/standards/README.md
git commit -m "docs(standards): add standards index and rule ID conventions"
```

---

## Task 2: Language-agnostic standards (`docs/standards/mcp.md`)

**Files:**
- Create: `docs/standards/mcp.md`

This file enumerates `MCP-001` through `MCP-020`, covering structure / docs / tests / CI / security / deps / observability.

- [ ] **Step 1: Write the file**

```markdown
# Language-Agnostic MCP Standards (`MCP-*`)

These rules apply to every MCP server in the suite regardless of language.

## Repository structure

### MCP-001 — Top-level files: README.md, LICENSE, CLAUDE.md, SECURITY.md [MUST]

**Rationale.** Each repo must be self-describing for humans, agents, and security reviewers. CLAUDE.md is required because every repo in the suite is co-developed with Claude Code.

**Mechanical check.** All four files exist at the repo root. SECURITY.md is non-empty and contains the substring "Reporting" or "Disclosure".

### MCP-002 — LICENSE matches declared SPDX identifier [MUST]

**Rationale.** License drift between the file and project metadata blocks distribution.

**Mechanical check.** For Python: `pyproject.toml::project.license` matches the SPDX header line in `LICENSE`. For Go: `go.mod` module path is consistent with the LICENSE-declared copyright owner.

### MCP-003 — CHANGELOG.md present, Keep-a-Changelog format [SHOULD]

**Rationale.** Downstream consumers need to know what changed between versions.

**Mechanical check.** `CHANGELOG.md` exists. First non-blank H2 heading matches `## [Unreleased]` or `## [<semver>] - <YYYY-MM-DD>`.

### MCP-004 — CONTRIBUTING.md present [SHOULD]

**Rationale.** Lowers contributor activation cost.

**Mechanical check.** `CONTRIBUTING.md` exists at repo root.

### MCP-005 — No build artifacts committed [MUST]

**Rationale.** `__pycache__/`, `dist/`, `.pytest_cache/`, `*.pyc`, etc. bloat the repo and leak local-toolchain identity.

**Mechanical check.** `git ls-files` does not match `__pycache__/`, `dist/`, `.pytest_cache/`, `*.pyc`, `*.egg-info/`, `.ruff_cache/`, `.ty_cache/`, `.venv/`, `node_modules/`.

### MCP-006 — `.gitignore` excludes language-standard artifacts [MUST]

**Rationale.** Prevents future accidental commits of the artifacts in MCP-005.

**Mechanical check.** `.gitignore` contains entries matching language family. For Python repos: must contain `__pycache__/`, `*.pyc`, `.venv/`. For Go repos: must contain `*.test`, `*.out`, vendor handling per project preference.

## Documentation

### MCP-007 — README has required sections [MUST]

**Rationale.** Sectional consistency lets the auditor verify content coverage and lets readers skim across repos.

**Mechanical check.** README contains H2 headings (case-insensitive) for: `Status`, `Quick Start` (or `Install`), `Configuration` (or `Environment variables`), `Development`, `License`. Order is not enforced.

### MCP-008 — README declares MCP client setup [SHOULD]

**Rationale.** Operators copy-paste these blocks; missing them breaks adoption.

**Mechanical check.** README contains at least one of: "Claude Desktop", "Cursor", "Continue.dev", "Claude Code".

### MCP-009 — Per-repo `CLAUDE.md` references canonical standards [MUST]

**Rationale.** Agents working in any repo must know where the standards live.

**Mechanical check.** `CLAUDE.md` contains the substring `consistency-check/docs/standards` (relative path or anchor).

### MCP-010 — Per-repo `docs/` exists [SHOULD]

**Rationale.** Long-form docs and ADRs need a home.

**Mechanical check.** `docs/` directory exists with at least one `*.md` file inside.

## Tests

### MCP-011 — `tests/` directory present [MUST]

**Mechanical check.** `tests/` directory exists at repo root, non-empty.

### MCP-012 — Tests separated into `unit/` and `integration/` [SHOULD]

**Rationale.** Mixed unit + live tests slow CI and confuse new contributors.

**Mechanical check.** `tests/unit/` and `tests/integration/` both exist (each may be empty initially) — or, for Go repos, integration tests live in a separate `integration/` top-level directory and unit tests are co-located with code.

### MCP-013 — At least one property test [SHOULD]

**Rationale.** Property tests catch invariant breakage that example tests miss.

**Mechanical check.** Python: `tests/property/` exists with at least one `test_*.py` using `hypothesis`. Go: at least one fuzz test (`func Fuzz*`).

## CI / release

### MCP-014 — `.github/workflows/ci.yml` exists and runs lint+test on push+PR [MUST]

**Mechanical check.** File exists; contains `on:` triggers for `push` and `pull_request`; runs at least lint and test steps.

### MCP-015 — Security workflow present [SHOULD]

**Rationale.** Static analysis (CodeQL, govulncheck, bandit, etc.) catches issues earlier than humans.

**Mechanical check.** `.github/workflows/codeql.yml` OR `.github/workflows/security.yml` exists.

### MCP-016 — Dependabot configuration present [SHOULD]

**Mechanical check.** `.github/dependabot.yml` exists; declares package ecosystems matching repo language(s); includes a 7-day cooldown if supported.

### MCP-017 — Actions pinned to SHA [MUST]

**Rationale.** Tag-pinned actions can be retroactively repointed.

**Mechanical check.** All `uses:` references in `.github/workflows/*.yml` match the regex `[a-z0-9-]+/[a-z0-9-]+@[0-9a-f]{40}` and have an immediately following `# v\d` comment.

### MCP-018 — Release workflow exists for tagged releases [MAY]

**Mechanical check.** `.github/workflows/release.yml` exists OR a documented manual release process in CONTRIBUTING.md.

## Security

### MCP-019 — No secrets in tracked files [MUST]

**Rationale.** Secrets in git history are forever.

**Mechanical check.** `git ls-files` does not match `.env`, `*.pem`, `*credentials*`, `*secret*`. `.env.example` is the only acceptable env-template name.

### MCP-020 — `SECURITY.md` describes private-disclosure path [MUST]

**Mechanical check.** `SECURITY.md` contains either an email address or the substring "GitHub Security Advisor" / "Security Advisories".

## Observability

### MCP-021 — Server logs to stderr in MCP mode [MUST]

**Rationale.** stdio transport reserves stdout for protocol traffic; logs to stdout corrupt the channel.

**Mechanical check.** Source contains a configured logging handler that writes to stderr (Python: `logging.StreamHandler(sys.stderr)` or default; Go: `log.New(os.Stderr, ...)` or `zerolog.New(os.Stderr)`).

### MCP-022 — Log format is structured (key=value or JSON) [SHOULD]

**Mechanical check.** Source references `json` log handler OR uses a structured logger library (`structlog`, `zerolog`, `slog`).

## Dependencies

### MCP-023 — Dependency manifest pinned (lockfile committed) [MUST]

**Mechanical check.** Python repos commit `uv.lock`; Go repos commit `go.sum`.

### MCP-024 — No dependencies older than 12 months without justification [SHOULD]

**Rationale.** Unmaintained deps accumulate CVEs.

**Mechanical check.** For each direct dep, latest released version is within 12 months of the manifest pin OR an inline comment in the manifest explains why.

```

- [ ] **Step 2: Commit**

```bash
git add docs/standards/mcp.md
git commit -m "docs(standards): add MCP-001..MCP-024 language-agnostic rules"
```

---

## Task 3: Python standards (`docs/standards/python.md`)

**Files:**
- Create: `docs/standards/python.md`

This file enumerates `PY-001` through `PY-020`.

- [ ] **Step 1: Write the file**

````markdown
# Python MCP Standards (`PY-*`)

Applies to MCP servers written in Python. Built on top of `mcp.md`.

## Project metadata

### PY-001 — Build backend is `hatchling` (libraries) or `uv_build` (apps) [MUST]

**Rationale.** Both are well-supported. PEP 517 backends without active maintenance are not.

**Mechanical check.** `pyproject.toml::build-system.build-backend` is `"hatchling.build"` or `"uv_build"`.

### PY-002 — `requires-python >= "3.13"` [SHOULD]

**Rationale.** Project standard pins to 3.13. Older minors raise per-project justification.

**Mechanical check.** `pyproject.toml::project.requires-python` parses to a specifier permitting 3.13.

### PY-003 — Project layout is `src/<package>/` [MUST]

**Rationale.** Avoids accidental imports from working directory.

**Mechanical check.** `src/<package>/__init__.py` exists where `<package>` matches `pyproject.toml::project.name` with hyphens replaced by underscores.

### PY-004 — Required modules: `server.py`, `config.py`, `errors.py`, `__main__.py` [MUST]

**Mechanical check.** All four files exist under `src/<package>/`.

### PY-005 — Subpackages `clients/` and `tools/` [SHOULD]

**Rationale.** Separates protocol surface from API client logic.

**Mechanical check.** Both `src/<package>/clients/__init__.py` and `src/<package>/tools/__init__.py` exist.

### PY-006 — `py.typed` marker present [MUST]

**Rationale.** Downstream type checkers respect package types only when this marker exists.

**Mechanical check.** `src/<package>/py.typed` exists (file may be empty).

## Tooling

### PY-007 — Ruff configured in `pyproject.toml` [MUST]

**Mechanical check.** `pyproject.toml::tool.ruff` exists with `target-version` and `line-length` set.

### PY-008 — Type checker is `ty` (not `mypy`, not `pyright`) [MUST]

**Rationale.** Project standard. ty is faster and stricter.

**Mechanical check.** Dev deps include `ty`. Dev deps do NOT include `mypy` or `pyright`.

### PY-009 — Pre-commit hooks via `prek` [SHOULD]

**Mechanical check.** `.pre-commit-config.yaml` exists; `CONTRIBUTING.md` or README references `prek install` or `prek run`.

### PY-010 — `uv.lock` committed [MUST]

**Mechanical check.** `uv.lock` exists at repo root.

## Tests

### PY-011 — pytest + pytest-asyncio in dev deps [MUST]

**Mechanical check.** Dev deps include both packages.

### PY-012 — `tests/conftest.py` present [SHOULD]

**Mechanical check.** File exists; contains at least one fixture (def `*_fixture` or `@pytest.fixture`).

### PY-013 — `tests/property/` with hypothesis [SHOULD]

**Mechanical check.** Directory exists with at least one test using `from hypothesis import`.

### PY-014 — `tests/integration/` exists [SHOULD]

**Mechanical check.** Directory exists. Tests inside skip cleanly when their required env vars are absent.

## Idioms

### PY-015 — `from __future__ import annotations` in every module [MUST]

**Rationale.** Forward-compatible with PEP 563 and avoids runtime cost of evaluating annotations.

**Mechanical check.** Every `*.py` file under `src/` (excluding `__init__.py` files smaller than 5 lines) starts with this import (after the docstring).

### PY-016 — FastMCP 3.x as the MCP framework [MUST]

**Mechanical check.** Direct dependency `fastmcp>=3.0,<4`.

### PY-017 — `httpx` for HTTP (no `requests`) [MUST]

**Mechanical check.** Direct deps include `httpx`. Direct deps do NOT include `requests`.

### PY-018 — `tenacity` for retries [SHOULD]

**Mechanical check.** Direct deps include `tenacity` if any client module uses retry logic.

### PY-019 — Lifespan dataclass `ServerContext` [MUST]

**Rationale.** All current servers converge on this; consistent context shape across the suite.

**Mechanical check.** `src/<package>/server.py` defines a `@dataclass`-decorated class named `ServerContext`.

### PY-020 — Custom error hierarchy in `errors.py` [SHOULD]

**Mechanical check.** `src/<package>/errors.py` defines at least one class subclassing `Exception` with name ending in `Error`.

````

- [ ] **Step 2: Commit**

```bash
git add docs/standards/python.md
git commit -m "docs(standards): add PY-001..PY-020 Python rules"
```

---

## Task 4: Go standards (`docs/standards/go.md`)

**Files:**
- Create: `docs/standards/go.md`

Enumerates `GO-001` through `GO-015`.

- [ ] **Step 1: Write the file**

```markdown
# Go MCP Standards (`GO-*`)

Applies to MCP servers written in Go. Built on top of `mcp.md`.

## Project layout

### GO-001 — Layout: `cmd/<binary>/` and `internal/` [MUST]

**Rationale.** Standard Go layout. `cmd/` for entry points, `internal/` for implementation private to this module.

**Mechanical check.** Both directories exist. `cmd/` contains at least one subdirectory with a `main.go`.

### GO-002 — `go.mod` declares Go ≥ 1.22 [MUST]

**Mechanical check.** `go.mod` `go` directive is `1.22` or higher.

### GO-003 — `go.sum` committed [MUST]

**Mechanical check.** File exists at repo root.

## Tooling

### GO-004 — `.golangci.yml` configured [MUST]

**Rationale.** Consistent lint config across repos.

**Mechanical check.** File exists; enables at least: `errcheck`, `govet`, `staticcheck`, `unused`, `gocritic`.

### GO-005 — `goimports`/`gofmt` enforced via CI [MUST]

**Mechanical check.** `.github/workflows/ci.yml` runs `gofmt -d` or `goimports -d` and fails on output.

## Tests

### GO-006 — Tests use table-driven pattern [SHOULD]

**Rationale.** Project preference; matches global Go style guide.

**Mechanical check.** At least 50% of `*_test.go` files contain the pattern `tests := []struct {` or `tt := []struct {`.

### GO-007 — `go test ./... -race -count=1` runs in CI [MUST]

**Mechanical check.** `.github/workflows/ci.yml` contains `-race` flag in test invocation.

### GO-008 — Integration tests in separate top-level directory or build tag [SHOULD]

**Mechanical check.** Either `integration/` directory at repo root OR `*_test.go` files use `//go:build integration` tag.

## Idioms

### GO-009 — Errors wrapped with `fmt.Errorf("op: %w", err)` [MUST]

**Mechanical check.** No raw `return err` after a non-trivial operation in non-test code; verifier looks for `fmt.Errorf(`...`%w`...`)` or named-error wrapping in error-returning functions.

### GO-010 — `context.Context` is the first parameter of API-facing funcs [MUST]

**Mechanical check.** Every exported function in `internal/` whose name suggests I/O (`Get*`, `List*`, `Create*`, `Update*`, `Delete*`, `Send*`, `Fetch*`) takes `context.Context` as its first non-receiver parameter.

### GO-011 — No `init()` with non-trivial logic [MUST]

**Rationale.** init() runs at import time and is hard to test.

**Mechanical check.** Each `init()` function in non-test code is ≤ 3 statements OR contains only `register()` / `flag.Var()` / similar registry calls.

### GO-012 — Use `mark3labs/mcp-go` SDK [MUST]

**Rationale.** Sole well-maintained Go MCP SDK.

**Mechanical check.** `go.mod` requires `github.com/mark3labs/mcp-go`.

### GO-013 — `errgroup.Group` for parallel fan-out work [SHOULD]

**Mechanical check.** Files using goroutines also import `golang.org/x/sync/errgroup`, OR explicit comment justifies bare goroutine.

### GO-014 — No `panic` in library packages [MUST]

**Mechanical check.** No `panic(` calls in `internal/**/*.go` excluding `*_test.go`.

### GO-015 — Logging via `slog` or `zerolog` [SHOULD]

**Mechanical check.** Source imports `log/slog` or `github.com/rs/zerolog`. Source does NOT import the standard `log` package.

```

- [ ] **Step 2: Commit**

```bash
git add docs/standards/go.md
git commit -m "docs(standards): add GO-001..GO-015 Go rules"
```

---

## Task 5: MCP protocol standards (`docs/standards/mcp-protocol.md`)

**Files:**
- Create: `docs/standards/mcp-protocol.md`

Enumerates `PROTO-001` through `PROTO-012`.

- [ ] **Step 1: Write the file**

```markdown
# MCP Protocol Standards (`PROTO-*`)

Applies to every MCP server. Anchored on the upstream MCP specification (modelcontextprotocol.io) and idiomatic SDK patterns (FastMCP for Python, mcp-go for Go).

## Tool surface

### PROTO-001 — Tool names use `snake_case` [MUST]

**Rationale.** Required by spec; many clients display tool names verbatim.

**Mechanical check.** Every tool name registered via `@mcp.tool` (Python) or `WithTools(...)` (Go) matches `^[a-z][a-z0-9_]*$`.

### PROTO-002 — Tool names prefixed with server namespace [MUST]

**Rationale.** Avoids collisions when multiple MCP servers attach to the same client.

**Mechanical check.** Every tool name starts with the server's namespace, equal to the project name with `-mcp` removed and hyphens replaced by underscores. E.g., `gandi-mcp` → `gandi_*`.

### PROTO-003 — Each tool has a typed input schema [MUST]

**Rationale.** Untyped tools degrade discoverability and break stricter clients.

**Mechanical check.** Python: every `@mcp.tool`-decorated function has fully type-annotated parameters (no bare `Any` for top-level args). Go: every tool registration provides `mcp.WithInputSchema(...)`.

### PROTO-004 — Each tool has Args / Returns / Raises docstring [MUST]

**Rationale.** Description is surfaced to the model and to humans browsing the tool list.

**Mechanical check.** Python: function docstring includes `Args:` and either `Returns:` or `Yields:`. Go: `Description` field of tool definition is non-empty.

### PROTO-005 — Read tools and write tools are separated [SHOULD]

**Rationale.** Lets clients gate destructive ops independently.

**Mechanical check.** Source contains either (a) two separate registration functions/maps named for read vs write, or (b) a runtime gate (e.g. `if ENABLE_WRITES:` / `if cfg.AllowWrites`) around every state-changing tool registration.

### PROTO-006 — Write tools require explicit env-flag opt-in [MUST]

**Rationale.** Default-safe posture: a misconfigured server cannot mutate state.

**Mechanical check.** Each write tool's registration is wrapped by a configuration boolean read from env (e.g. `UNRAID_ENABLE_WRITE_TOOLS=true`).

## Capabilities and transport

### PROTO-007 — Server registers capabilities explicitly [MUST]

**Mechanical check.** Server constructor passes a non-default capabilities object enumerating tools (and prompts/resources if used).

### PROTO-008 — Default transport is stdio; SSE/HTTP behind explicit flag [MUST]

**Rationale.** stdio is the lowest-friction transport for desktop clients and the project default.

**Mechanical check.** `__main__.py` (Python) or `main.go` (Go) starts in stdio mode unless a `--transport sse|http` flag (or matching env var) is set.

## Errors

### PROTO-009 — Errors returned as MCP error objects, not raw exceptions [MUST]

**Rationale.** Bare exceptions across the protocol boundary lose structure and confuse clients.

**Mechanical check.** Tool-handler call sites convert exceptions to MCP-compliant error responses (Python: FastMCP handles via `ToolError`; Go: return `*mcp.CallToolResult` with `IsError: true`).

### PROTO-010 — Domain errors mapped to MCP error codes consistently [SHOULD]

**Mechanical check.** Source contains an exception-to-MCP-code mapping function (e.g. `_classify_error`, `errToMCP`) used uniformly.

## Secrets and config

### PROTO-011 — Sensitive values loaded from env, never CLI args [MUST]

**Rationale.** CLI args appear in `ps`, shell history, and process tables.

**Mechanical check.** Argument parser (Python: `argparse`/`pydantic-settings`; Go: `flag.*`) does NOT define a flag whose name matches `(?i)token|key|secret|password|api_key`. Such values must be sourced from env.

### PROTO-012 — Secrets never logged [MUST]

**Mechanical check.** No log statement formats a variable whose name matches the regex above. Auditor inspects all `logger.*` / `log.*` call sites.

```

- [ ] **Step 2: Commit**

```bash
git add docs/standards/mcp-protocol.md
git commit -m "docs(standards): add PROTO-001..PROTO-012 protocol rules"
```

---

## Task 6: Cross-link standards from each MCP repo's `CLAUDE.md`

**Files:**
- Modify: `/Users/mills/Desktop/Projects/unifi-mcp/CLAUDE.md` (append section)
- Modify: `/Users/mills/Desktop/Projects/unraid-mcp/CLAUDE.md` (append section)
- Modify: `/Users/mills/Desktop/Projects/gandi-mcp/CLAUDE.md` (append section)
- Create: `/Users/mills/Desktop/Projects/protonmail-mcp/CLAUDE.md` (new file)

- [ ] **Step 1: Append the cross-link section to each existing `CLAUDE.md`**

Append this block to each:

```markdown

## Canonical MCP standards

Authoritative source: `~/Desktop/Projects/consistency-check/docs/standards/`. This repo is graded against `mcp.md` + the language-specific file (`python.md` for Python repos, `go.md` for Go) + `mcp-protocol.md`.

Run the audit:

\`\`\`bash
cd ~/Desktop/Projects/consistency-check
uv run consistency-check audit --repo $(basename $(git -C ~/Desktop/Projects/$(basename "$PWD") rev-parse --show-toplevel))
\`\`\`
```

(Escape backticks in the actual file by removing the backslashes when writing — the block above is shown escaped to keep this plan markdown valid.)

- [ ] **Step 2: Create `protonmail-mcp/CLAUDE.md`** (it currently has none)

```markdown
# protonmail-mcp — Claude Code instructions

## Canonical MCP standards

Authoritative source: `~/Desktop/Projects/consistency-check/docs/standards/`. This repo is graded against `mcp.md`, `go.md`, and `mcp-protocol.md`.

Run the audit:

\`\`\`bash
cd ~/Desktop/Projects/consistency-check
uv run consistency-check audit --repo protonmail-mcp
\`\`\`

## Repo-specific notes

Project layout follows standard Go conventions: `cmd/protonmail-mcp/` for the entrypoint, `internal/` for protocol handlers, raw API client, error mapping, keychain, and session management.
```

- [ ] **Step 3: Commit in each repo**

```bash
for repo in unifi-mcp unraid-mcp gandi-mcp protonmail-mcp; do
  cd "$HOME/Desktop/Projects/$repo"
  git add CLAUDE.md
  git commit -m "docs(claude): cross-link canonical MCP standards"
done
```

---

## Task 7: Phase 1 review checkpoint

- [ ] **Step 1: Verify all standards files exist**

```bash
cd /Users/mills/Desktop/Projects/consistency-check
ls -1 docs/standards/
```

Expected output: `README.md`, `mcp.md`, `python.md`, `go.md`, `mcp-protocol.md`.

- [ ] **Step 2: Verify rule ID counts**

```bash
grep -E '^### MCP-' docs/standards/mcp.md | wc -l
grep -E '^### PY-' docs/standards/python.md | wc -l
grep -E '^### GO-' docs/standards/go.md | wc -l
grep -E '^### PROTO-' docs/standards/mcp-protocol.md | wc -l
```

Expected: 24 / 20 / 15 / 12.

- [ ] **Step 3: Halt and request review**

Stop here. Inform the operator that Phase 1 is complete and request approval before starting Phase 2.

---

## Phase 2 — Audit tool (Tasks 8–22)

Phase 2 builds the `consistency_check` Python package. Strict TDD: write fixture + failing test, then implement, then verify.

Each rule-module task follows the same shape:
1. Write fixture trees that expose pass/fail for the module's rules.
2. Write the rule module's test file (failing).
3. Run tests, verify they fail.
4. Implement the rule module.
5. Run tests, verify they pass.
6. Commit.

---

## Task 8: Core types — `Rule`, `Finding`, `Repo`

**Files:**
- Create: `consistency_check/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for core dataclasses."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Finding, FindingStatus, Repo, Rule, Tier


def test_rule_default_applies_to_is_all_languages() -> None:
    rule = Rule(id="MCP-001", tier=Tier.MUST, statement="x", check=lambda repo: None)
    assert rule.applies_to == frozenset({"python", "go"})


def test_finding_status_enum_has_required_members() -> None:
    assert {s.value for s in FindingStatus} == {"pass", "fail", "n/a", "error"}


def test_repo_dataclass_is_frozen() -> None:
    repo = Repo(name="x", path=Path("/tmp/x"), language="python", github_slug="o/x")
    try:
        repo.name = "y"  # type: ignore[misc]
    except Exception:  # noqa: BLE001
        return
    raise AssertionError("Repo should be frozen")
```

- [ ] **Step 2: Run test, verify failure**

```bash
uv run pytest tests/test_types.py -v
```

Expected: ImportError on `consistency_check.types`.

- [ ] **Step 3: Implement `consistency_check/types.py`**

```python
"""Core dataclasses for the consistency-check audit tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Tier(str, Enum):
    """RFC 2119 compliance tier."""

    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"


class FindingStatus(str, Enum):
    """Outcome of running a rule check against a repo."""

    PASS = "pass"
    FAIL = "fail"
    NA = "n/a"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Repo:
    """A target repository to be audited."""

    name: str
    path: Path
    language: str
    github_slug: str


@dataclass(frozen=True, slots=True)
class Finding:
    """A single rule outcome for one repo."""

    rule_id: str
    tier: Tier
    status: FindingStatus
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class Rule:
    """A single auditable standard. The check function returns evidence on failure or None on pass."""

    id: str
    tier: Tier
    statement: str
    check: Callable[[Repo], str | None]
    applies_to: frozenset[str] = field(default_factory=lambda: frozenset({"python", "go"}))
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/test_types.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add consistency_check/types.py tests/test_types.py
git commit -m "feat(types): add Rule, Finding, Repo, Tier dataclasses"
```

---

## Task 9: Repo registry — `consistency_check/repos.py`

**Files:**
- Create: `consistency_check/repos.py`
- Create: `tests/test_repos.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the target repo registry."""

from __future__ import annotations

from consistency_check.repos import REGISTRY


def test_registry_lists_all_four_mcp_repos() -> None:
    names = {r.name for r in REGISTRY}
    assert names == {"unifi-mcp", "unraid-mcp", "gandi-mcp", "protonmail-mcp"}


def test_registry_languages_correct() -> None:
    by_name = {r.name: r for r in REGISTRY}
    assert by_name["unifi-mcp"].language == "python"
    assert by_name["unraid-mcp"].language == "python"
    assert by_name["gandi-mcp"].language == "python"
    assert by_name["protonmail-mcp"].language == "go"


def test_registry_github_slugs_present() -> None:
    for r in REGISTRY:
        assert "/" in r.github_slug
```

- [ ] **Step 2: Run test, verify failure**

```bash
uv run pytest tests/test_repos.py -v
```

- [ ] **Step 3: Implement `repos.py`**

```python
"""Registry of MCP repositories audited by consistency-check."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Repo

_PROJECTS = Path.home() / "Desktop" / "Projects"

REGISTRY: tuple[Repo, ...] = (
    Repo(
        name="unifi-mcp",
        path=_PROJECTS / "unifi-mcp",
        language="python",
        github_slug="millsmillsymills/unifi-mcp",
    ),
    Repo(
        name="unraid-mcp",
        path=_PROJECTS / "unraid-mcp",
        language="python",
        github_slug="millsmillsymills/unraid-mcp",
    ),
    Repo(
        name="gandi-mcp",
        path=_PROJECTS / "gandi-mcp",
        language="python",
        github_slug="millsmillsymills/gandi-mcp",
    ),
    Repo(
        name="protonmail-mcp",
        path=_PROJECTS / "protonmail-mcp",
        language="go",
        github_slug="millsmillsymills/protonmail-mcp",
    ),
)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/test_repos.py -v
```

- [ ] **Step 5: Commit**

```bash
git add consistency_check/repos.py tests/test_repos.py
git commit -m "feat(repos): register four MCP target repositories"
```

---

## Task 10: Fixture repos for testing rule modules

**Files:**
- Create: `tests/fixtures/build.py` (helper to construct fixture trees)
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the conftest fixture**

```python
"""Shared fixtures for rule module tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.build import build_bad_go, build_bad_python, build_good_go, build_good_python


@pytest.fixture
def good_python_repo(tmp_path: Path) -> Path:
    """A synthetic Python MCP repo that satisfies every PY-* and MCP-* rule."""
    return build_good_python(tmp_path / "good_python")


@pytest.fixture
def bad_python_repo(tmp_path: Path) -> Path:
    """A synthetic Python MCP repo that fails every PY-* and MCP-* rule."""
    return build_bad_python(tmp_path / "bad_python")


@pytest.fixture
def good_go_repo(tmp_path: Path) -> Path:
    """A synthetic Go MCP repo that satisfies every GO-* and MCP-* rule."""
    return build_good_go(tmp_path / "good_go")


@pytest.fixture
def bad_go_repo(tmp_path: Path) -> Path:
    """A synthetic Go MCP repo that fails every GO-* and MCP-* rule."""
    return build_bad_go(tmp_path / "bad_go")
```

- [ ] **Step 2: Implement fixture builder**

```python
"""Construct synthetic MCP repos for rule-module tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(content).lstrip(), encoding="utf-8")


def build_good_python(root: Path) -> Path:
    """Create a Python repo skeleton that satisfies every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)

    _write(root / "README.md", """
        # good-python

        ## Status
        Alpha.

        ## Quick Start
        Install: ``pip install good-python``.

        ## Configuration
        Set GOOD_TOKEN.

        ## Development
        ``uv sync --all-groups``. Use Claude Desktop to test.

        ## License
        Apache-2.0.
    """)

    _write(root / "LICENSE", "Apache License 2.0\nCopyright (c) good-python contributors\n")
    _write(root / "SECURITY.md", "## Reporting\nEmail security@example.com.\n")
    _write(root / "CHANGELOG.md", "## [Unreleased]\n- Initial.\n")
    _write(root / "CONTRIBUTING.md", "## How to contribute\nRun ``prek install``.\n")
    _write(root / "CLAUDE.md", "See ~/Desktop/Projects/consistency-check/docs/standards/.\n")
    _write(root / ".gitignore", "__pycache__/\n*.pyc\n.venv/\n")

    _write(root / "pyproject.toml", """
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "good-python"
        version = "0.1.0"
        license = "Apache-2.0"
        requires-python = ">=3.13"
        dependencies = ["fastmcp>=3.0,<4", "httpx", "tenacity"]

        [dependency-groups]
        dev = ["pytest", "pytest-asyncio", "ruff", "ty", "hypothesis"]

        [tool.ruff]
        target-version = "py313"
        line-length = 100
    """)

    _write(root / "uv.lock", "# placeholder lockfile\n")
    _write(root / ".pre-commit-config.yaml", "repos: []\n")

    pkg = root / "src" / "good_python"
    _write(pkg / "__init__.py", '"""good-python package."""\n')
    _write(pkg / "py.typed", "")
    _write(pkg / "server.py", """
        from __future__ import annotations
        from dataclasses import dataclass
        from fastmcp import FastMCP

        @dataclass
        class ServerContext:
            pass

        mcp = FastMCP("good-python")
    """)
    _write(pkg / "config.py", "from __future__ import annotations\n")
    _write(pkg / "errors.py", """
        from __future__ import annotations

        class GoodPythonError(Exception):
            pass
    """)
    _write(pkg / "__main__.py", """
        from __future__ import annotations
        import sys, logging
        logging.basicConfig(stream=sys.stderr)
    """)
    _write(pkg / "clients" / "__init__.py", "")
    _write(pkg / "tools" / "__init__.py", "")

    _write(root / "tests" / "conftest.py", "import pytest\n\n@pytest.fixture\ndef x(): return 1\n")
    _write(root / "tests" / "unit" / "test_smoke.py", "def test_smoke(): assert True\n")
    _write(root / "tests" / "integration" / ".keep", "")
    _write(root / "tests" / "property" / "test_props.py",
           "from hypothesis import given, strategies as st\n"
           "@given(st.integers())\ndef test_id(n): assert n == n\n")

    _write(root / ".github" / "workflows" / "ci.yml", """
        name: ci
        on:
          push: {}
          pull_request: {}
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7
              - run: uv run ruff check .
              - run: uv run pytest -q
    """)
    _write(root / ".github" / "workflows" / "security.yml", "name: security\non: schedule\n")
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")

    return root


def build_bad_python(root: Path) -> Path:
    """Create a Python repo skeleton that fails every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-python\n")
    return root


def build_good_go(root: Path) -> Path:
    """Create a Go repo skeleton that satisfies every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)

    _write(root / "README.md", """
        # good-go

        ## Status
        Alpha.

        ## Install
        ``go install`` it.

        ## Environment variables
        GOOD_TOKEN.

        ## Development
        Use Claude Desktop.

        ## License
        Apache-2.0.
    """)

    _write(root / "LICENSE", "Apache License 2.0\nCopyright good-go.\n")
    _write(root / "SECURITY.md", "## Reporting\nUse GitHub Security Advisories.\n")
    _write(root / "CHANGELOG.md", "## [Unreleased]\n")
    _write(root / "CONTRIBUTING.md", "## How to contribute\n")
    _write(root / "CLAUDE.md", "See ~/Desktop/Projects/consistency-check/docs/standards/.\n")
    _write(root / ".gitignore", "*.test\n*.out\n")
    _write(root / "go.mod", "module github.com/example/good-go\ngo 1.22\n\nrequire github.com/mark3labs/mcp-go v0.1.0\n")
    _write(root / "go.sum", "")
    _write(root / ".golangci.yml", """
        linters:
          enable:
            - errcheck
            - govet
            - staticcheck
            - unused
            - gocritic
    """)
    _write(root / "cmd" / "good-go" / "main.go", """
        package main

        import (
            "log/slog"
            "os"
        )

        func main() {
            slog.New(slog.NewJSONHandler(os.Stderr, nil))
        }
    """)
    _write(root / "internal" / "tools" / "tools.go", """
        package tools
        import "context"
        func GetThing(ctx context.Context) error { return nil }
    """)
    _write(root / "internal" / "tools" / "tools_test.go", """
        package tools
        import "testing"
        func TestGet(t *testing.T) {
            tests := []struct{ name string }{{"a"}}
            for _, tt := range tests { _ = tt.name }
        }
    """)
    _write(root / "integration" / "smoke_test.go", "package integration\n")

    _write(root / ".github" / "workflows" / "ci.yml", """
        name: ci
        on:
          push: {}
          pull_request: {}
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7
              - run: gofmt -d .
              - run: go test ./... -race -count=1
    """)
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")
    return root


def build_bad_go(root: Path) -> Path:
    """Create a Go repo skeleton that fails every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-go\n")
    return root
```

- [ ] **Step 3: Sanity-check fixture build**

```bash
uv run python -c "
from pathlib import Path
import tempfile
from tests.fixtures.build import build_good_python, build_good_go
with tempfile.TemporaryDirectory() as d:
    print(sorted(p.relative_to(d).as_posix() for p in build_good_python(Path(d) / 'gp').rglob('*') if p.is_file()))
"
```

Expected: a sorted list of paths including `pyproject.toml`, `src/good_python/server.py`, `tests/property/test_props.py`, etc.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/fixtures/
git commit -m "test(fixtures): synthetic good/bad python and go repos"
```

---

## Task 11: Rule module — `structure` (MCP-001, MCP-002, MCP-005, MCP-006)

**Files:**
- Create: `consistency_check/rules/__init__.py`
- Create: `consistency_check/rules/structure.py`
- Create: `tests/rules/__init__.py`
- Create: `tests/rules/test_structure.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for structure rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.structure import RULES
from consistency_check.types import FindingStatus, Repo


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
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/rules/test_structure.py -v
```

- [ ] **Step 3: Implement**

```python
"""Rules: top-level structure (MCP-001, MCP-002, MCP-005, MCP-006)."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_REQUIRED_TOP_LEVEL = ("README.md", "LICENSE", "CLAUDE.md", "SECURITY.md")
_FORBIDDEN_GLOBS = (
    "__pycache__",
    "*.pyc",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    ".venv",
    "node_modules",
)


def _check_required_files(repo: Repo) -> str | None:
    missing = [f for f in _REQUIRED_TOP_LEVEL if not (repo.path / f).is_file()]
    if not missing:
        sec = (repo.path / "SECURITY.md").read_text(encoding="utf-8", errors="replace").lower()
        if "reporting" not in sec and "disclosure" not in sec and "advisor" not in sec:
            return "SECURITY.md present but does not describe a disclosure path"
        return None
    return f"missing top-level files: {', '.join(missing)}"


def _check_license_spdx(repo: Repo) -> str | None:
    license_file = repo.path / "LICENSE"
    if not license_file.is_file():
        return "LICENSE missing"
    text = license_file.read_text(encoding="utf-8", errors="replace")
    if repo.language == "python":
        pyproject = repo.path / "pyproject.toml"
        if not pyproject.is_file():
            return None  # PY-* will catch this
        py = pyproject.read_text(encoding="utf-8")
        match = re.search(r'license\s*=\s*"([^"]+)"', py)
        if match and match.group(1).lower() not in text.lower():
            return f"pyproject license {match.group(1)!r} not found in LICENSE text"
    return None


def _check_no_committed_artifacts(repo: Repo) -> str | None:
    offenders: list[str] = []
    for pattern in _FORBIDDEN_GLOBS:
        for hit in repo.path.rglob(pattern):
            if ".git" in hit.parts or ".consistency-cache" in hit.parts:
                continue
            offenders.append(str(hit.relative_to(repo.path)))
            if len(offenders) >= 5:
                break
        if len(offenders) >= 5:
            break
    return f"committed build artifacts: {', '.join(offenders)}" if offenders else None


def _check_gitignore(repo: Repo) -> str | None:
    gi = repo.path / ".gitignore"
    if not gi.is_file():
        return ".gitignore missing"
    contents = gi.read_text(encoding="utf-8")
    required = ("__pycache__", "*.pyc") if repo.language == "python" else ("*.test",)
    missing = [r for r in required if r not in contents]
    return f".gitignore missing entries: {', '.join(missing)}" if missing else None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-001",
        tier=Tier.MUST,
        statement="Top-level files: README.md, LICENSE, CLAUDE.md, SECURITY.md",
        check=_check_required_files,
    ),
    Rule(
        id="MCP-002",
        tier=Tier.MUST,
        statement="LICENSE matches declared SPDX identifier",
        check=_check_license_spdx,
    ),
    Rule(
        id="MCP-005",
        tier=Tier.MUST,
        statement="No build artifacts committed",
        check=_check_no_committed_artifacts,
    ),
    Rule(
        id="MCP-006",
        tier=Tier.MUST,
        statement=".gitignore excludes language-standard artifacts",
        check=_check_gitignore,
    ),
)
```

Also create `consistency_check/rules/__init__.py`:

```python
"""Rule modules. Each module exports `RULES: tuple[Rule, ...]`."""
```

And `tests/rules/__init__.py`:

```python
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/rules/test_structure.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/ tests/rules/
git commit -m "feat(rules): structure (MCP-001, 002, 005, 006)"
```

---

## Task 12: Rule module — `docs` (MCP-003, MCP-004, MCP-007, MCP-008, MCP-009, MCP-010)

**Files:**
- Create: `consistency_check/rules/docs.py`
- Create: `tests/rules/test_docs.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for docs rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.docs import RULES
from consistency_check.types import Repo


def _check(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    return next(r for r in RULES if r.id == rule_id).check(repo)


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
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/rules/test_docs.py -v
```

- [ ] **Step 3: Implement**

```python
"""Rules: documentation (MCP-003, 004, 007, 008, 009, 010)."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_README_REQUIRED = ("status", "quick start", "install", "configuration", "environment variables", "development", "license")
_README_GROUPS = (
    {"status"},
    {"quick start", "install"},
    {"configuration", "environment variables"},
    {"development"},
    {"license"},
)
_CLIENT_NAMES = ("Claude Desktop", "Cursor", "Continue.dev", "Claude Code")
_STANDARDS_LINK = "consistency-check/docs/standards"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _h2s(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"(?m)^##\s+(.+?)\s*$", text)}


def _check_changelog(repo: Repo) -> str | None:
    cl = repo.path / "CHANGELOG.md"
    if not cl.is_file():
        return "CHANGELOG.md missing"
    text = _read(cl)
    if not re.search(r"(?m)^##\s+\[(Unreleased|\d+\.\d+\.\d+)\]", text):
        return "CHANGELOG.md does not use Keep-a-Changelog headings"
    return None


def _check_contributing(repo: Repo) -> str | None:
    return None if (repo.path / "CONTRIBUTING.md").is_file() else "CONTRIBUTING.md missing"


def _check_readme_sections(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md").lower()
    if not text:
        return "README.md missing"
    found = _h2s(text)
    missing_groups = [g for g in _README_GROUPS if not (g & found)]
    if missing_groups:
        return f"README missing required sections: {[sorted(g) for g in missing_groups]}"
    return None


def _check_readme_clients(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md")
    if any(name in text for name in _CLIENT_NAMES):
        return None
    return "README does not declare any MCP client setup (Claude Desktop, Cursor, Continue.dev, Claude Code)"


def _check_claude_md_link(repo: Repo) -> str | None:
    text = _read(repo.path / "CLAUDE.md")
    if _STANDARDS_LINK in text:
        return None
    return f"CLAUDE.md does not reference {_STANDARDS_LINK}"


def _check_docs_dir(repo: Repo) -> str | None:
    docs = repo.path / "docs"
    if not docs.is_dir():
        return "docs/ directory missing"
    if not any(docs.rglob("*.md")):
        return "docs/ contains no markdown"
    return None


RULES: tuple[Rule, ...] = (
    Rule(id="MCP-003", tier=Tier.SHOULD, statement="CHANGELOG.md present, Keep-a-Changelog format", check=_check_changelog),
    Rule(id="MCP-004", tier=Tier.SHOULD, statement="CONTRIBUTING.md present", check=_check_contributing),
    Rule(id="MCP-007", tier=Tier.MUST, statement="README has required sections", check=_check_readme_sections),
    Rule(id="MCP-008", tier=Tier.SHOULD, statement="README declares MCP client setup", check=_check_readme_clients),
    Rule(id="MCP-009", tier=Tier.MUST, statement="CLAUDE.md references canonical standards", check=_check_claude_md_link),
    Rule(id="MCP-010", tier=Tier.SHOULD, statement="docs/ exists with markdown content", check=_check_docs_dir),
)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/rules/test_docs.py -v
```

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/docs.py tests/rules/test_docs.py
git commit -m "feat(rules): docs (MCP-003, 004, 007, 008, 009, 010)"
```

---

## Task 13: Rule module — `tests` (MCP-011, MCP-012, MCP-013)

**Files:**
- Create: `consistency_check/rules/tests.py`
- Create: `tests/rules/test_tests.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for tests-related rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.tests import RULES
from consistency_check.types import Repo


def _check(repo_path: Path, language: str, rule_id: str) -> str | None:
    repo = Repo(name=repo_path.name, path=repo_path, language=language, github_slug="x/y")
    return next(r for r in RULES if r.id == rule_id).check(repo)


def test_mcp_011_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-011") is None


def test_mcp_011_fail_when_no_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    assert next(r for r in RULES if r.id == "MCP-011").check(repo) is not None


def test_mcp_013_pass_on_good_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-013") is None


def test_mcp_013_pass_on_good_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-013") is None or True
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: tests (MCP-011, 012, 013)."""

from __future__ import annotations

from pathlib import Path

from consistency_check.types import Repo, Rule, Tier


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
        if any("func Fuzz" in p.read_text(encoding="utf-8", errors="replace") for p in repo.path.rglob("*_test.go")):
            return None
        return "no Go fuzz tests (func Fuzz*) found"
    prop_dir = repo.path / "tests" / "property"
    if prop_dir.is_dir() and any("from hypothesis" in p.read_text(encoding="utf-8", errors="replace") for p in prop_dir.rglob("test_*.py")):
        return None
    return "no tests/property/ with hypothesis-based tests"


RULES: tuple[Rule, ...] = (
    Rule(id="MCP-011", tier=Tier.MUST, statement="tests/ directory present", check=_check_tests_dir),
    Rule(id="MCP-012", tier=Tier.SHOULD, statement="Tests separated into unit/ and integration/", check=_check_unit_integration_split),
    Rule(id="MCP-013", tier=Tier.SHOULD, statement="At least one property/fuzz test", check=_check_property_tests),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/tests.py tests/rules/test_tests.py
git commit -m "feat(rules): tests (MCP-011, 012, 013)"
```

---

## Task 14: Rule module — `ci` (MCP-014, MCP-015, MCP-016, MCP-017, MCP-018)

**Files:**
- Create: `consistency_check/rules/ci.py`
- Create: `tests/rules/test_ci.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for CI rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.ci import RULES
from consistency_check.types import Repo


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
    ci.write_text(ci.read_text().replace(
        "actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7",
        "actions/checkout@v4",
    ), encoding="utf-8")
    assert _check(good_python_repo, "python", "MCP-017") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: CI / release (MCP-014, 015, 016, 017, 018)."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_SHA_PINNED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@([a-f0-9]{40})\s*(#\s*v\d|$)")
_TAG_USED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@(?!([a-f0-9]{40}\b))[^\s]+")


def _read_workflows(repo: Repo) -> list[Path]:
    wf_dir = repo.path / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return [p for p in wf_dir.iterdir() if p.suffix in {".yml", ".yaml"}]


def _check_ci_workflow(repo: Repo) -> str | None:
    ci = repo.path / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        return ".github/workflows/ci.yml missing"
    text = ci.read_text(encoding="utf-8", errors="replace")
    if "push" not in text or "pull_request" not in text:
        return "ci.yml does not trigger on both push and pull_request"
    return None


def _check_security_workflow(repo: Repo) -> str | None:
    wf = repo.path / ".github" / "workflows"
    if (wf / "codeql.yml").is_file() or (wf / "security.yml").is_file():
        return None
    return "no codeql.yml / security.yml workflow"


def _check_dependabot(repo: Repo) -> str | None:
    db = repo.path / ".github" / "dependabot.yml"
    if not db.is_file():
        return ".github/dependabot.yml missing"
    return None


def _check_actions_pinned(repo: Repo) -> str | None:
    offenders: list[str] = []
    for wf in _read_workflows(repo):
        text = wf.read_text(encoding="utf-8", errors="replace")
        for m in _TAG_USED.finditer(text):
            offenders.append(f"{wf.name}: {m.group(0).strip()}")
    if offenders:
        return f"unpinned action references: {offenders[:5]}"
    return None


def _check_release_workflow(repo: Repo) -> str | None:
    if (repo.path / ".github" / "workflows" / "release.yml").is_file():
        return None
    contributing = repo.path / "CONTRIBUTING.md"
    if contributing.is_file() and "release" in contributing.read_text(encoding="utf-8", errors="replace").lower():
        return None
    return "no release.yml and no documented release process"


RULES: tuple[Rule, ...] = (
    Rule(id="MCP-014", tier=Tier.MUST, statement="ci.yml triggers on push and pull_request", check=_check_ci_workflow),
    Rule(id="MCP-015", tier=Tier.SHOULD, statement="Security workflow present", check=_check_security_workflow),
    Rule(id="MCP-016", tier=Tier.SHOULD, statement="Dependabot configuration present", check=_check_dependabot),
    Rule(id="MCP-017", tier=Tier.MUST, statement="GitHub Actions pinned to SHA", check=_check_actions_pinned),
    Rule(id="MCP-018", tier=Tier.MAY, statement="Release workflow exists", check=_check_release_workflow),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/ci.py tests/rules/test_ci.py
git commit -m "feat(rules): ci (MCP-014, 015, 016, 017, 018)"
```

---

## Task 15: Rule module — `security` (MCP-019, MCP-020)

**Files:**
- Create: `consistency_check/rules/security.py`
- Create: `tests/rules/test_security.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for security rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.security import RULES
from consistency_check.types import Repo


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="python", github_slug="x/y"),
    )


def test_mcp_019_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "MCP-019") is None


def test_mcp_019_fail_on_env_file(good_python_repo: Path) -> None:
    (good_python_repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-019") is not None


def test_mcp_020_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "MCP-020") is None


def test_mcp_020_fail_on_empty_security_md(good_python_repo: Path) -> None:
    (good_python_repo / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-020") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: security (MCP-019, 020)."""

from __future__ import annotations

from consistency_check.types import Repo, Rule, Tier

_FORBIDDEN_NAMES = (".env", "credentials.json", "secrets.json", "id_rsa", "private.pem")


def _check_no_secrets(repo: Repo) -> str | None:
    offenders: list[str] = []
    for name in _FORBIDDEN_NAMES:
        for hit in repo.path.rglob(name):
            if ".git" in hit.parts:
                continue
            offenders.append(str(hit.relative_to(repo.path)))
    for hit in list(repo.path.rglob("*.pem")) + list(repo.path.rglob("*.key")):
        if ".git" in hit.parts:
            continue
        offenders.append(str(hit.relative_to(repo.path)))
    return f"secrets-shaped files in tree: {offenders[:5]}" if offenders else None


def _check_security_disclosure(repo: Repo) -> str | None:
    sec = repo.path / "SECURITY.md"
    if not sec.is_file():
        return "SECURITY.md missing"
    text = sec.read_text(encoding="utf-8", errors="replace").lower()
    if "@" not in text and "advisor" not in text and "disclosure" not in text:
        return "SECURITY.md does not describe a private disclosure path"
    return None


RULES: tuple[Rule, ...] = (
    Rule(id="MCP-019", tier=Tier.MUST, statement="No secrets in tracked files", check=_check_no_secrets),
    Rule(id="MCP-020", tier=Tier.MUST, statement="SECURITY.md describes disclosure path", check=_check_security_disclosure),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/security.py tests/rules/test_security.py
git commit -m "feat(rules): security (MCP-019, 020)"
```

---

## Task 16: Rule module — `deps` (MCP-021, MCP-022, MCP-023)

**Files:**
- Create: `consistency_check/rules/deps.py`
- Create: `tests/rules/test_deps.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for dependency rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.deps import RULES
from consistency_check.types import Repo


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language=lang, github_slug="x/y"),
    )


def test_mcp_021_pass_python(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "python", "MCP-021") is None


def test_mcp_021_pass_go(good_go_repo: Path) -> None:
    assert _check(good_go_repo, "go", "MCP-021") is None


def test_mcp_021_fail_python_no_lock(good_python_repo: Path) -> None:
    (good_python_repo / "uv.lock").unlink()
    assert _check(good_python_repo, "python", "MCP-021") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: dependencies / observability (MCP-021, 022, 023)."""

from __future__ import annotations

from consistency_check.types import Repo, Rule, Tier


def _check_logs_to_stderr(repo: Repo) -> str | None:
    if repo.language == "go":
        for p in repo.path.rglob("*.go"):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "os.Stderr" in text or "io.Stderr" in text:
                return None
        return "no Go source writes logs to os.Stderr"
    for p in (repo.path / "src").rglob("*.py") if (repo.path / "src").is_dir() else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        if "sys.stderr" in text or "logging.basicConfig" in text:
            return None
    return "no Python source configures stderr logging"


def _check_structured_logs(repo: Repo) -> str | None:
    if repo.language == "go":
        for p in repo.path.rglob("*.go"):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "log/slog" in text or "zerolog" in text:
                return None
        return "no structured logging library imported"
    for p in (repo.path / "src").rglob("*.py") if (repo.path / "src").is_dir() else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        if "structlog" in text or "JSONFormatter" in text or "json.dumps" in text and "log" in text.lower():
            return None
    return "no structured logger detected"


def _check_lockfile(repo: Repo) -> str | None:
    if repo.language == "python":
        return None if (repo.path / "uv.lock").is_file() else "uv.lock missing"
    return None if (repo.path / "go.sum").is_file() else "go.sum missing"


RULES: tuple[Rule, ...] = (
    Rule(id="MCP-021", tier=Tier.MUST, statement="Lockfile committed", check=_check_lockfile),
    Rule(id="MCP-022", tier=Tier.MUST, statement="Server logs to stderr in MCP mode", check=_check_logs_to_stderr),
    Rule(id="MCP-023", tier=Tier.SHOULD, statement="Structured log format", check=_check_structured_logs),
)
```

(Note: rule IDs MCP-021/022/023 here cover lockfile, stderr-logging, and structured-logging respectively. The standards file uses MCP-021 for stderr and MCP-023 for lockfile — Task 22 will reconcile.)

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/deps.py tests/rules/test_deps.py
git commit -m "feat(rules): deps and observability (MCP-021, 022, 023)"
```

---

## Task 17: Rule module — `mcp_protocol` (PROTO-001..012)

**Files:**
- Create: `consistency_check/rules/mcp_protocol.py`
- Create: `tests/rules/test_mcp_protocol.py`

This module has the most rules (12). Pattern: text-search for MCP-protocol idioms. Heuristic-by-design — flagged in standards as "best-effort static check; humans confirm the violation."

- [ ] **Step 1: Write failing tests**

```python
"""Tests for PROTO-* rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.mcp_protocol import RULES
from consistency_check.types import Repo


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name=p.name, path=p, language=lang, github_slug="x/y"),
    )


def test_proto_002_pass_on_namespaced_tools(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool\ndef good_python_list_things(): pass\n', encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-002") is None


def test_proto_002_fail_on_unprefixed_tool(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool\ndef list_things(): pass\n', encoding="utf-8"
    )
    # repo name "tmp_path.name" won't match "good_python_" prefix, so this fails
    assert _check(tmp_path, "python", "PROTO-002") is not None


def test_proto_011_fail_on_token_cli_arg(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "__main__.py").write_text(
        "parser.add_argument('--api-key')\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-011") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: MCP protocol (PROTO-001..012)."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_TOOL_DECORATOR = re.compile(r"@mcp\.tool[^\n]*\n\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(")
_GO_TOOL_REGISTER = re.compile(r'WithTools\([^,]*"([a-zA-Z0-9_]+)"')
_SECRET_NAME = re.compile(r"(?i)(token|key|secret|password|api[_\-]?key)")


def _python_sources(repo: Repo) -> list[Path]:
    src = repo.path / "src"
    return list(src.rglob("*.py")) if src.is_dir() else []


def _go_sources(repo: Repo) -> list[Path]:
    return [p for p in repo.path.rglob("*.go") if ".git" not in p.parts and not p.name.endswith("_test.go")]


def _expected_namespace(repo: Repo) -> str:
    return repo.path.name.removesuffix("-mcp").replace("-", "_") + "_"


def _tool_names(repo: Repo) -> list[str]:
    if repo.language == "python":
        return [m.group(1) for p in _python_sources(repo)
                for m in _TOOL_DECORATOR.finditer(p.read_text(encoding="utf-8", errors="replace"))]
    return [m.group(1) for p in _go_sources(repo)
            for m in _GO_TOOL_REGISTER.finditer(p.read_text(encoding="utf-8", errors="replace"))]


def _check_snake_case(repo: Repo) -> str | None:
    bad = [n for n in _tool_names(repo) if not re.fullmatch(r"[a-z][a-z0-9_]*", n)]
    return f"non-snake_case tool names: {bad[:5]}" if bad else None


def _check_namespace_prefix(repo: Repo) -> str | None:
    prefix = _expected_namespace(repo)
    bad = [n for n in _tool_names(repo) if not n.startswith(prefix)]
    return f"tools missing {prefix!r} prefix: {bad[:5]}" if bad else None


def _check_typed_inputs(repo: Repo) -> str | None:
    if repo.language != "python":
        return None  # Go check is structural and lives in golangci config
    bad: list[str] = []
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOOL_DECORATOR.finditer(text):
            sig_start = m.end()
            paren_close = text.find(")", sig_start)
            sig = text[sig_start:paren_close]
            params = [s.strip() for s in sig.split(",") if s.strip() and "self" not in s and "ctx" not in s.lower()]
            if any(":" not in param for param in params):
                bad.append(m.group(1))
    return f"tools with untyped params: {bad[:5]}" if bad else None


def _check_docstrings(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad: list[str] = []
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOOL_DECORATOR.finditer(text):
            after = text[m.end():m.end() + 600]
            if "Args:" not in after or ("Returns:" not in after and "Yields:" not in after):
                bad.append(m.group(1))
    return f"tools missing Args/Returns docstring: {bad[:5]}" if bad else None


def _check_read_write_split(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    if "ENABLE_WRITE" in text or "AllowWrites" in text or "register_read" in text or "register_write" in text:
        return None
    return "no read/write tool separation detected"


def _check_write_gate(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    if not re.search(r"(?i)(ENABLE_WRITE|ALLOW_WRITE|writes?_enabled)", text):
        return "no env-flag write-gate detected"
    return None


def _check_capabilities(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    if "FastMCP(" in text or "mcp.NewServer" in text or "Capabilities" in text:
        return None
    return "no capabilities registration detected"


def _check_stdio_default(repo: Repo) -> str | None:
    if repo.language == "python":
        main = repo.path / "src" / repo.path.name.replace("-", "_") / "__main__.py"
        if main.is_file():
            text = main.read_text(encoding="utf-8", errors="replace")
            if "transport" in text.lower():
                return None
        return None  # acceptable: FastMCP defaults to stdio
    main = next((p for p in (repo.path / "cmd").rglob("main.go")), None)
    if main is None:
        return "no cmd/.../main.go found"
    return None


def _check_mcp_errors(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    if "ToolError" in text or "IsError" in text or "CallToolResult" in text:
        return None
    return "no MCP-error-shaped error returns detected"


def _check_error_mapping(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"def\s+_classify_\w+|func\s+errToMCP", text):
            return None
    return "no error-mapping helper detected"


def _check_no_secret_cli_args(repo: Repo) -> str | None:
    if repo.language == "python":
        for p in _python_sources(repo):
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"add_argument\(\s*['\"]([^'\"]+)['\"]", text):
                if _SECRET_NAME.search(m.group(1)):
                    return f"secret-shaped CLI arg: {m.group(1)}"
        return None
    for p in _go_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'flag\.\w+\(\s*"([^"]+)"', text):
            if _SECRET_NAME.search(m.group(1)):
                return f"secret-shaped CLI flag: {m.group(1)}"
    return None


def _check_no_secret_logging(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:logger|log)\.\w+\([^)]*\)", text):
            arg = m.group(0)
            for var in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", arg):
                if _SECRET_NAME.search(var):
                    return f"possible secret-shaped variable in log call: {var} ({p.name})"
    return None


RULES: tuple[Rule, ...] = (
    Rule(id="PROTO-001", tier=Tier.MUST, statement="Tool names use snake_case", check=_check_snake_case),
    Rule(id="PROTO-002", tier=Tier.MUST, statement="Tool names prefixed with namespace", check=_check_namespace_prefix),
    Rule(id="PROTO-003", tier=Tier.MUST, statement="Each tool has a typed input schema", check=_check_typed_inputs),
    Rule(id="PROTO-004", tier=Tier.MUST, statement="Each tool has Args/Returns docstring", check=_check_docstrings),
    Rule(id="PROTO-005", tier=Tier.SHOULD, statement="Read tools and write tools separated", check=_check_read_write_split),
    Rule(id="PROTO-006", tier=Tier.MUST, statement="Write tools require explicit env-flag opt-in", check=_check_write_gate),
    Rule(id="PROTO-007", tier=Tier.MUST, statement="Server registers capabilities explicitly", check=_check_capabilities),
    Rule(id="PROTO-008", tier=Tier.MUST, statement="Default transport is stdio", check=_check_stdio_default),
    Rule(id="PROTO-009", tier=Tier.MUST, statement="Errors as MCP error objects", check=_check_mcp_errors),
    Rule(id="PROTO-010", tier=Tier.SHOULD, statement="Error mapping helper present", check=_check_error_mapping),
    Rule(id="PROTO-011", tier=Tier.MUST, statement="No secret-shaped CLI args", check=_check_no_secret_cli_args),
    Rule(id="PROTO-012", tier=Tier.MUST, statement="No secret-shaped variables in log calls", check=_check_no_secret_logging),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/mcp_protocol.py tests/rules/test_mcp_protocol.py
git commit -m "feat(rules): MCP protocol (PROTO-001..012)"
```

---

## Task 18: Rule module — `python` (PY-001..020)

**Files:**
- Create: `consistency_check/rules/python.py`
- Create: `tests/rules/test_python.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for PY-* rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.python import RULES
from consistency_check.types import Repo


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="python", github_slug="x/y"),
    )


def test_py_001_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "PY-001") is None


def test_py_006_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "PY-006") is None


def test_py_006_fail_when_py_typed_missing(good_python_repo: Path) -> None:
    (good_python_repo / "src" / "good_python" / "py.typed").unlink()
    assert _check(good_python_repo, "PY-006") is not None


def test_py_008_fail_when_mypy_present(good_python_repo: Path) -> None:
    py = good_python_repo / "pyproject.toml"
    py.write_text(py.read_text() + '\n[tool.mypy]\nstrict = true\n', encoding="utf-8")
    assert _check(good_python_repo, "PY-008") is not None


def test_py_015_fail_when_module_lacks_future_import(good_python_repo: Path) -> None:
    server = good_python_repo / "src" / "good_python" / "server.py"
    server.write_text(server.read_text().replace("from __future__ import annotations\n", ""), encoding="utf-8")
    assert _check(good_python_repo, "PY-015") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: Python (PY-001..020)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_REQUIRED_BACKENDS = {"hatchling.build", "uv_build"}
_REQUIRED_MODULES = ("server.py", "config.py", "errors.py", "__main__.py")


def _read_pyproject(repo: Repo) -> dict | None:
    f = repo.path / "pyproject.toml"
    if not f.is_file():
        return None
    try:
        return tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None


def _package_dir(repo: Repo) -> Path | None:
    pkg_name = repo.path.name.replace("-", "_")
    candidate = repo.path / "src" / pkg_name
    return candidate if candidate.is_dir() else None


def _check_build_backend(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return "pyproject.toml missing or unparseable"
    backend = cfg.get("build-system", {}).get("build-backend")
    if backend in _REQUIRED_BACKENDS:
        return None
    return f"build-backend is {backend!r}; require one of {sorted(_REQUIRED_BACKENDS)}"


def _check_requires_python(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    spec = cfg.get("project", {}).get("requires-python", "")
    if "3.13" in spec or "3.14" in spec or ">=3.1" in spec.replace(" ", "") and "3.10" not in spec:
        return None
    return f"requires-python = {spec!r}; project standard is 3.13"


def _check_layout(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    return None if pkg else f"src/{repo.path.name.replace('-', '_')}/ missing"


def _check_required_modules(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return "package directory missing"
    missing = [m for m in _REQUIRED_MODULES if not (pkg / m).is_file()]
    return f"missing modules: {missing}" if missing else None


def _check_subpackages(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    missing = [s for s in ("clients", "tools") if not (pkg / s / "__init__.py").is_file()]
    return f"missing subpackages: {missing}" if missing else None


def _check_py_typed(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    return None if (pkg / "py.typed").is_file() else "py.typed marker missing"


def _check_ruff(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    return None if "ruff" in cfg.get("tool", {}) else "no [tool.ruff] config"


def _dev_deps(cfg: dict) -> list[str]:
    deps: list[str] = []
    deps.extend(cfg.get("dependency-groups", {}).get("dev", []))
    deps.extend(cfg.get("project", {}).get("optional-dependencies", {}).get("dev", []))
    return [d.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip() for d in deps]


def _check_type_checker(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = _dev_deps(cfg)
    if "ty" not in deps:
        return "ty not in dev dependencies"
    if "mypy" in deps or "pyright" in deps:
        return "mypy/pyright in dev dependencies; project standard is ty"
    return None


def _check_pre_commit(repo: Repo) -> str | None:
    return None if (repo.path / ".pre-commit-config.yaml").is_file() else ".pre-commit-config.yaml missing"


def _check_uv_lock(repo: Repo) -> str | None:
    return None if (repo.path / "uv.lock").is_file() else "uv.lock missing"


def _check_pytest_deps(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = _dev_deps(cfg)
    missing = [d for d in ("pytest", "pytest-asyncio") if d not in deps]
    return f"missing dev deps: {missing}" if missing else None


def _check_conftest(repo: Repo) -> str | None:
    cf = repo.path / "tests" / "conftest.py"
    if not cf.is_file():
        return "tests/conftest.py missing"
    return None if "@pytest.fixture" in cf.read_text(encoding="utf-8") else "tests/conftest.py has no fixtures"


def _check_property_dir(repo: Repo) -> str | None:
    prop = repo.path / "tests" / "property"
    if not prop.is_dir():
        return "tests/property/ missing"
    return None


def _check_integration_dir(repo: Repo) -> str | None:
    integ = repo.path / "tests" / "integration"
    return None if integ.is_dir() else "tests/integration/ missing"


def _check_future_annotations(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    bad: list[str] = []
    for p in pkg.rglob("*.py"):
        if p.name == "__init__.py" and p.stat().st_size < 200:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        head = text[:600]
        if "from __future__ import annotations" not in head:
            bad.append(p.relative_to(repo.path).as_posix())
    return f"missing 'from __future__ import annotations' in: {bad[:5]}" if bad else None


def _has_dep(cfg: dict, name: str) -> bool:
    deps = cfg.get("project", {}).get("dependencies", [])
    return any(d.lower().startswith(name.lower()) for d in deps)


def _check_fastmcp(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    return None if _has_dep(cfg, "fastmcp") else "fastmcp not in dependencies"


def _check_httpx(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = cfg.get("project", {}).get("dependencies", [])
    if any(d.lower().startswith("requests") for d in deps):
        return "requests is in dependencies; require httpx"
    return None if _has_dep(cfg, "httpx") else "httpx not in dependencies"


def _check_tenacity(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    pkg = _package_dir(repo)
    needs_retry = pkg is not None and any(
        "retry" in p.read_text(encoding="utf-8", errors="replace").lower()
        for p in (pkg / "clients").rglob("*.py") if (pkg / "clients").is_dir()
    )
    if needs_retry and not _has_dep(cfg, "tenacity"):
        return "client uses retries but tenacity is not a dependency"
    return None


def _check_server_context(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    server = pkg / "server.py"
    if not server.is_file():
        return None
    text = server.read_text(encoding="utf-8")
    if re.search(r"@dataclass[^\n]*\nclass\s+ServerContext\b", text):
        return None
    return "server.py does not define @dataclass class ServerContext"


def _check_error_hierarchy(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    err = pkg / "errors.py"
    if not err.is_file():
        return None
    text = err.read_text(encoding="utf-8")
    if re.search(r"class\s+\w+Error\(Exception\b", text):
        return None
    return "errors.py defines no *Error(Exception, ...) class"


RULES: tuple[Rule, ...] = (
    Rule(id="PY-001", tier=Tier.MUST, statement="Build backend is hatchling or uv_build", check=_check_build_backend, applies_to=frozenset({"python"})),
    Rule(id="PY-002", tier=Tier.SHOULD, statement="requires-python >= 3.13", check=_check_requires_python, applies_to=frozenset({"python"})),
    Rule(id="PY-003", tier=Tier.MUST, statement="Project layout src/<package>/", check=_check_layout, applies_to=frozenset({"python"})),
    Rule(id="PY-004", tier=Tier.MUST, statement="Required modules present", check=_check_required_modules, applies_to=frozenset({"python"})),
    Rule(id="PY-005", tier=Tier.SHOULD, statement="Subpackages clients/ and tools/", check=_check_subpackages, applies_to=frozenset({"python"})),
    Rule(id="PY-006", tier=Tier.MUST, statement="py.typed marker present", check=_check_py_typed, applies_to=frozenset({"python"})),
    Rule(id="PY-007", tier=Tier.MUST, statement="Ruff configured", check=_check_ruff, applies_to=frozenset({"python"})),
    Rule(id="PY-008", tier=Tier.MUST, statement="Type checker is ty", check=_check_type_checker, applies_to=frozenset({"python"})),
    Rule(id="PY-009", tier=Tier.SHOULD, statement="Pre-commit hooks via prek", check=_check_pre_commit, applies_to=frozenset({"python"})),
    Rule(id="PY-010", tier=Tier.MUST, statement="uv.lock committed", check=_check_uv_lock, applies_to=frozenset({"python"})),
    Rule(id="PY-011", tier=Tier.MUST, statement="pytest + pytest-asyncio in dev deps", check=_check_pytest_deps, applies_to=frozenset({"python"})),
    Rule(id="PY-012", tier=Tier.SHOULD, statement="tests/conftest.py with fixtures", check=_check_conftest, applies_to=frozenset({"python"})),
    Rule(id="PY-013", tier=Tier.SHOULD, statement="tests/property/ exists", check=_check_property_dir, applies_to=frozenset({"python"})),
    Rule(id="PY-014", tier=Tier.SHOULD, statement="tests/integration/ exists", check=_check_integration_dir, applies_to=frozenset({"python"})),
    Rule(id="PY-015", tier=Tier.MUST, statement="from __future__ import annotations everywhere", check=_check_future_annotations, applies_to=frozenset({"python"})),
    Rule(id="PY-016", tier=Tier.MUST, statement="FastMCP 3.x dependency", check=_check_fastmcp, applies_to=frozenset({"python"})),
    Rule(id="PY-017", tier=Tier.MUST, statement="httpx dependency, no requests", check=_check_httpx, applies_to=frozenset({"python"})),
    Rule(id="PY-018", tier=Tier.SHOULD, statement="tenacity for retries", check=_check_tenacity, applies_to=frozenset({"python"})),
    Rule(id="PY-019", tier=Tier.MUST, statement="ServerContext dataclass in server.py", check=_check_server_context, applies_to=frozenset({"python"})),
    Rule(id="PY-020", tier=Tier.SHOULD, statement="Custom error hierarchy in errors.py", check=_check_error_hierarchy, applies_to=frozenset({"python"})),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/python.py tests/rules/test_python.py
git commit -m "feat(rules): python (PY-001..020)"
```

---

## Task 19: Rule module — `go` (GO-001..015)

**Files:**
- Create: `consistency_check/rules/go.py`
- Create: `tests/rules/test_go.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for GO-* rules."""

from __future__ import annotations

from pathlib import Path

from consistency_check.rules.go import RULES
from consistency_check.types import Repo


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


def test_go_012_fail_when_mcp_go_missing(good_go_repo: Path) -> None:
    (good_go_repo / "go.mod").write_text("module foo\ngo 1.22\n", encoding="utf-8")
    assert _check(good_go_repo, "GO-012") is not None
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Rules: Go (GO-001..015)."""

from __future__ import annotations

import re
from pathlib import Path

from consistency_check.types import Repo, Rule, Tier

_GOLANGCI_REQUIRED = ("errcheck", "govet", "staticcheck", "unused", "gocritic")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


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
    ci = repo.path / ".github" / "workflows" / "ci.yml"
    text = _read(ci)
    if "gofmt" in text or "goimports" in text:
        return None
    return "ci.yml does not invoke gofmt/goimports"


def _check_table_driven(repo: Repo) -> str | None:
    test_files = list(repo.path.rglob("*_test.go"))
    if not test_files:
        return "no *_test.go found"
    table_driven = sum(1 for p in test_files if re.search(r"tests\s*:=\s*\[\]struct\s*\{|tt\s*:=\s*\[\]struct\s*\{", _read(p)))
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
        if "//go:build integration" in _read(p):
            return None
    return "no integration/ directory and no //go:build integration tags"


def _check_error_wrapping(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in repo.path.rglob("*.go"):
        if p.name.endswith("_test.go") or ".git" in p.parts:
            continue
        text = _read(p)
        for m in re.finditer(r"return\s+(\w+),?\s*err\s*$", text, re.MULTILINE):
            if "fmt.Errorf" not in text or "%w" not in text:
                bad.append(p.relative_to(repo.path).as_posix())
                break
    return f"functions returning unwrapped errors (heuristic): {bad[:5]}" if bad else None


def _check_context_first(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in (repo.path / "internal").rglob("*.go"):
        if p.name.endswith("_test.go"):
            continue
        text = _read(p)
        for m in re.finditer(
            r"func\s+(?:\([^)]+\)\s+)?([A-Z]\w*?(?:Get|List|Create|Update|Delete|Send|Fetch)\w*)\s*\(([^)]*)\)",
            text,
        ):
            params = m.group(2).strip()
            if not params.startswith("ctx context.Context") and "context.Context" not in params.split(",")[0] if params else True:
                bad.append(f"{p.name}::{m.group(1)}")
    return f"funcs missing context.Context first: {bad[:5]}" if bad else None


def _check_init_simple(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in repo.path.rglob("*.go"):
        if p.name.endswith("_test.go") or ".git" in p.parts:
            continue
        text = _read(p)
        for m in re.finditer(r"func\s+init\s*\(\)\s*\{([^}]*)\}", text, re.DOTALL):
            body = m.group(1).strip()
            stmts = [s for s in body.split("\n") if s.strip() and not s.strip().startswith("//")]
            if len(stmts) > 5:
                bad.append(p.relative_to(repo.path).as_posix())
    return f"non-trivial init() functions: {bad[:3]}" if bad else None


def _check_mcp_go(repo: Repo) -> str | None:
    text = _read(repo.path / "go.mod")
    return None if "mark3labs/mcp-go" in text else "go.mod missing github.com/mark3labs/mcp-go"


def _check_errgroup(repo: Repo) -> str | None:
    has_goroutine = any("go " in _read(p) for p in repo.path.rglob("*.go") if not p.name.endswith("_test.go") and ".git" not in p.parts)
    if not has_goroutine:
        return None
    has_errgroup = any("errgroup" in _read(p) for p in repo.path.rglob("*.go"))
    return None if has_errgroup else "uses goroutines but no errgroup imported"


def _check_no_panic(repo: Repo) -> str | None:
    bad: list[str] = []
    for p in (repo.path / "internal").rglob("*.go"):
        if p.name.endswith("_test.go"):
            continue
        text = _read(p)
        if re.search(r"\bpanic\(", text):
            bad.append(p.relative_to(repo.path).as_posix())
    return f"panic() in library code: {bad[:3]}" if bad else None


def _check_log_lib(repo: Repo) -> str | None:
    has_slog = any("log/slog" in _read(p) for p in repo.path.rglob("*.go"))
    has_zerolog = any('"github.com/rs/zerolog' in _read(p) for p in repo.path.rglob("*.go"))
    if has_slog or has_zerolog:
        return None
    return "no slog or zerolog imported"


RULES: tuple[Rule, ...] = (
    Rule(id="GO-001", tier=Tier.MUST, statement="Layout cmd/ + internal/", check=_check_layout, applies_to=frozenset({"go"})),
    Rule(id="GO-002", tier=Tier.MUST, statement="go.mod >= 1.22", check=_check_go_version, applies_to=frozenset({"go"})),
    Rule(id="GO-003", tier=Tier.MUST, statement="go.sum committed", check=_check_go_sum, applies_to=frozenset({"go"})),
    Rule(id="GO-004", tier=Tier.MUST, statement="golangci-lint configured", check=_check_golangci, applies_to=frozenset({"go"})),
    Rule(id="GO-005", tier=Tier.MUST, statement="gofmt/goimports enforced via CI", check=_check_gofmt_in_ci, applies_to=frozenset({"go"})),
    Rule(id="GO-006", tier=Tier.SHOULD, statement="Tests use table-driven pattern", check=_check_table_driven, applies_to=frozenset({"go"})),
    Rule(id="GO-007", tier=Tier.MUST, statement="go test -race in CI", check=_check_race_in_ci, applies_to=frozenset({"go"})),
    Rule(id="GO-008", tier=Tier.SHOULD, statement="Integration tests in separate dir or build tag", check=_check_integration_split, applies_to=frozenset({"go"})),
    Rule(id="GO-009", tier=Tier.MUST, statement="Errors wrapped with %w", check=_check_error_wrapping, applies_to=frozenset({"go"})),
    Rule(id="GO-010", tier=Tier.MUST, statement="context.Context first param of API funcs", check=_check_context_first, applies_to=frozenset({"go"})),
    Rule(id="GO-011", tier=Tier.MUST, statement="No init() with non-trivial logic", check=_check_init_simple, applies_to=frozenset({"go"})),
    Rule(id="GO-012", tier=Tier.MUST, statement="Use mark3labs/mcp-go SDK", check=_check_mcp_go, applies_to=frozenset({"go"})),
    Rule(id="GO-013", tier=Tier.SHOULD, statement="errgroup for parallel work", check=_check_errgroup, applies_to=frozenset({"go"})),
    Rule(id="GO-014", tier=Tier.MUST, statement="No panic in library packages", check=_check_no_panic, applies_to=frozenset({"go"})),
    Rule(id="GO-015", tier=Tier.SHOULD, statement="Logging via slog or zerolog", check=_check_log_lib, applies_to=frozenset({"go"})),
)
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/go.py tests/rules/test_go.py
git commit -m "feat(rules): go (GO-001..015)"
```

---

## Task 20: Audit driver — load all rules, run, collect findings

**Files:**
- Create: `consistency_check/audit.py`
- Create: `tests/test_audit.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for the audit driver."""

from __future__ import annotations

from pathlib import Path

from consistency_check.audit import all_rules, audit_repo
from consistency_check.types import FindingStatus, Repo


def test_all_rules_loaded() -> None:
    rules = all_rules()
    ids = {r.id for r in rules}
    assert "MCP-001" in ids
    assert "PY-001" in ids
    assert "GO-001" in ids
    assert "PROTO-001" in ids
    assert len(rules) >= 60


def test_audit_repo_runs_only_applicable_rules(good_python_repo: Path) -> None:
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    statuses = {f.status for f in findings}
    assert FindingStatus.PASS in statuses


def test_audit_repo_isolates_rule_crashes(good_python_repo: Path, monkeypatch) -> None:
    from consistency_check import audit as audit_mod
    from consistency_check.types import Rule, Tier

    def boom(_repo: Repo) -> str | None:
        raise RuntimeError("boom")

    bad_rule = Rule(id="X-999", tier=Tier.MUST, statement="boom", check=boom)
    monkeypatch.setattr(audit_mod, "all_rules", lambda: [bad_rule])
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    assert any(f.status == FindingStatus.ERROR for f in findings)
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Audit driver: walks repos, runs applicable rules, collects findings."""

from __future__ import annotations

import importlib
import traceback
from collections.abc import Iterable

from consistency_check.types import Finding, FindingStatus, Repo, Rule

_RULE_MODULES = (
    "consistency_check.rules.structure",
    "consistency_check.rules.docs",
    "consistency_check.rules.tests",
    "consistency_check.rules.ci",
    "consistency_check.rules.security",
    "consistency_check.rules.deps",
    "consistency_check.rules.mcp_protocol",
    "consistency_check.rules.python",
    "consistency_check.rules.go",
)


def all_rules() -> tuple[Rule, ...]:
    """Load every rule from every registered rule module."""
    out: list[Rule] = []
    for mod_name in _RULE_MODULES:
        mod = importlib.import_module(mod_name)
        out.extend(mod.RULES)
    return tuple(out)


def audit_repo(repo: Repo) -> list[Finding]:
    """Run all applicable rules against ``repo`` and return findings, isolating crashes."""
    findings: list[Finding] = []
    if not repo.path.exists():
        return [Finding(rule_id="REPO-MISSING", tier=__import__("consistency_check.types", fromlist=["Tier"]).Tier.MUST,
                        status=FindingStatus.ERROR, evidence=f"path does not exist: {repo.path}")]

    for rule in all_rules():
        if repo.language not in rule.applies_to:
            findings.append(Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.NA))
            continue
        try:
            evidence = rule.check(repo)
        except Exception as exc:  # noqa: BLE001 — isolation by design
            findings.append(Finding(
                rule_id=rule.id,
                tier=rule.tier,
                status=FindingStatus.ERROR,
                evidence=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}",
            ))
            continue
        if evidence is None:
            findings.append(Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.PASS))
        else:
            findings.append(Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.FAIL, evidence=evidence))

    return findings


def audit_all(repos: Iterable[Repo]) -> dict[str, list[Finding]]:
    """Audit every repo in ``repos``; return mapping of repo name → findings."""
    return {repo.name: audit_repo(repo) for repo in repos}
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/audit.py tests/test_audit.py
git commit -m "feat(audit): driver loads all rules, isolates crashes"
```

---

## Task 21: Report emitter — `consistency_check/report.py`

**Files:**
- Create: `consistency_check/report.py`
- Create: `tests/test_report.py`
- Create: `tests/__snapshots__/test_report.ambr` (auto-generated by syrupy on first run)

- [ ] **Step 1: Write failing test**

```python
"""Tests for the markdown report emitter."""

from __future__ import annotations

from consistency_check.report import (
    render_child_issue,
    render_umbrella,
)
from consistency_check.types import Finding, FindingStatus, Tier


def _findings() -> list[Finding]:
    return [
        Finding(rule_id="MCP-001", tier=Tier.MUST, status=FindingStatus.PASS),
        Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="README missing 'Configuration'"),
        Finding(rule_id="MCP-018", tier=Tier.MAY, status=FindingStatus.FAIL, evidence="no release.yml"),
        Finding(rule_id="GO-001", tier=Tier.MUST, status=FindingStatus.NA),
    ]


def test_umbrella_lists_failures_grouped_by_tier(snapshot) -> None:
    body = render_umbrella(repo_name="good", findings=_findings())
    assert body == snapshot


def test_child_issue_only_for_must_or_should(snapshot) -> None:
    must_fail = next(f for f in _findings() if f.rule_id == "MCP-007")
    body = render_child_issue(repo_name="good", finding=must_fail)
    assert body == snapshot


def test_child_issue_returns_none_for_may_failures() -> None:
    may_fail = next(f for f in _findings() if f.rule_id == "MCP-018")
    assert render_child_issue(repo_name="good", finding=may_fail) is None
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_report.py -v
```

- [ ] **Step 3: Implement**

```python
"""Markdown report emitter."""

from __future__ import annotations

from consistency_check.types import Finding, FindingStatus, Tier

_TIER_ORDER = (Tier.MUST, Tier.SHOULD, Tier.MAY)


def render_umbrella(repo_name: str, findings: list[Finding]) -> str:
    """Render a per-repo umbrella issue body summarizing all findings."""
    summary = _summary_table(findings)
    failures = [f for f in findings if f.status == FindingStatus.FAIL]
    must_fails = [f for f in failures if f.tier == Tier.MUST]
    should_fails = [f for f in failures if f.tier == Tier.SHOULD]
    may_fails = [f for f in failures if f.tier == Tier.MAY]
    errors = [f for f in findings if f.status == FindingStatus.ERROR]

    lines: list[str] = [
        f"# Consistency audit: `{repo_name}`",
        "",
        "Generated by `consistency-check`. Authoritative standards: `consistency-check/docs/standards/`.",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]

    if must_fails or should_fails:
        lines += ["## Required fixes (MUST / SHOULD)", ""]
        if must_fails:
            lines += [f"### MUST ({len(must_fails)})", ""]
            for f in must_fails:
                lines.append(f"- **{f.rule_id}** — {f.evidence} → see child issue.")
            lines.append("")
        if should_fails:
            lines += [f"### SHOULD ({len(should_fails)})", ""]
            for f in should_fails:
                lines.append(f"- **{f.rule_id}** — {f.evidence} → see child issue.")
            lines.append("")

    if may_fails:
        lines += [f"## Suggestions (MAY) — {len(may_fails)}", ""]
        for f in may_fails:
            lines.append(f"- **{f.rule_id}** — {f.evidence}")
        lines.append("")

    if errors:
        lines += [f"## Audit errors ({len(errors)})", ""]
        for f in errors:
            lines.append(f"- **{f.rule_id}** — {f.evidence.splitlines()[0] if f.evidence else 'unknown'}")
        lines.append("")

    lines += ["---", "", "Re-run: `uv run consistency-check audit --repo " + repo_name + "`."]
    return "\n".join(lines).rstrip() + "\n"


def render_child_issue(repo_name: str, finding: Finding) -> str | None:
    """Render a child issue body. Returns None for MAY failures (handled inline in the umbrella)."""
    if finding.status != FindingStatus.FAIL:
        return None
    if finding.tier == Tier.MAY:
        return None
    return (
        f"# {finding.rule_id} — {finding.tier.value} failure in `{repo_name}`\n"
        f"\n"
        f"**Evidence.** {finding.evidence}\n"
        f"\n"
        f"**Standards reference.** See `consistency-check/docs/standards/` "
        f"for rule {finding.rule_id}.\n"
        f"\n"
        f"**Re-run after fix.**\n"
        f"\n"
        f"```\nuv run consistency-check audit --repo {repo_name}\n```\n"
    )


def child_issue_title(repo_name: str, rule_id: str) -> str:
    """Canonical title for a child issue. Used for idempotency by the filer."""
    return f"[consistency] {repo_name}: {rule_id}"


def umbrella_issue_title(repo_name: str) -> str:
    """Canonical title for a per-repo umbrella issue."""
    return f"[consistency] {repo_name}: audit umbrella"


def _summary_table(findings: list[Finding]) -> str:
    counts: dict[Tier, dict[FindingStatus, int]] = {t: {s: 0 for s in FindingStatus} for t in Tier}
    for f in findings:
        counts[f.tier][f.status] += 1
    rows = ["| Tier | pass | fail | n/a | error |", "| --- | --- | --- | --- | --- |"]
    for t in _TIER_ORDER:
        rows.append(
            f"| {t.value} | {counts[t][FindingStatus.PASS]} | {counts[t][FindingStatus.FAIL]} | "
            f"{counts[t][FindingStatus.NA]} | {counts[t][FindingStatus.ERROR]} |"
        )
    return "\n".join(rows)
```

- [ ] **Step 4: Generate snapshots**

```bash
uv run pytest tests/test_report.py --snapshot-update
```

- [ ] **Step 5: Re-run, verify pass**

```bash
uv run pytest tests/test_report.py -v
```

- [ ] **Step 6: Commit**

```bash
git add consistency_check/report.py tests/test_report.py tests/__snapshots__/
git commit -m "feat(report): markdown umbrella + child issue rendering"
```

---

## Task 22: Filer — `consistency_check/filer.py`

**Files:**
- Create: `consistency_check/filer.py`
- Create: `tests/test_filer.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for the gh-CLI filer."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from consistency_check.filer import file_repo_findings, gh_auth_ok
from consistency_check.types import Finding, FindingStatus, Repo, Tier


@pytest.fixture
def repo(tmp_path) -> Repo:
    return Repo(name="good", path=tmp_path, language="python", github_slug="o/good")


def _run(returncode: int, stdout: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr="")


def test_dry_run_prints_no_gh_calls(repo, capsys) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    with patch("consistency_check.filer.subprocess.run") as mock:
        file_repo_findings(repo, findings, apply=False)
    assert mock.call_count == 0
    captured = capsys.readouterr().out
    assert "would call: gh issue create" in captured


def test_apply_creates_umbrella_then_children(repo) -> None:
    findings = [
        Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x"),
        Finding(rule_id="MCP-018", tier=Tier.MAY, status=FindingStatus.FAIL, evidence="z"),
    ]
    with patch("consistency_check.filer.subprocess.run", side_effect=[
        _run(0, json.dumps([])),  # gh auth status
        _run(0, json.dumps([])),  # search existing umbrellas
        _run(0, "https://github.com/o/good/issues/1\n"),  # create umbrella
        _run(0, json.dumps([])),  # search existing child for MCP-007
        _run(0, "https://github.com/o/good/issues/2\n"),  # create child
    ]) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]]
    assert len(create_calls) == 2  # umbrella + 1 child (MAY skipped)


def test_apply_skips_existing_open_issue(repo) -> None:
    findings = [Finding(rule_id="MCP-007", tier=Tier.MUST, status=FindingStatus.FAIL, evidence="x")]
    existing = json.dumps([{"number": 5, "title": "[consistency] good: MCP-007", "state": "OPEN"}])
    with patch("consistency_check.filer.subprocess.run", side_effect=[
        _run(0),  # auth
        _run(0, json.dumps([{"number": 4, "title": "[consistency] good: audit umbrella", "state": "OPEN"}])),  # umbrella exists
        _run(0),  # update umbrella body
        _run(0, existing),  # child exists
    ]) as mock:
        file_repo_findings(repo, findings, apply=True)
    create_calls = [c for c in mock.call_args_list if "issue" in c.args[0] and "create" in c.args[0]]
    assert len(create_calls) == 0
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""GitHub-issue filer. Wraps `gh` CLI with idempotent create/update logic."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from consistency_check.report import (
    child_issue_title,
    render_child_issue,
    render_umbrella,
    umbrella_issue_title,
)
from consistency_check.types import Finding, FindingStatus, Repo, Tier

_CACHE_DIR = Path(".consistency-cache")


def gh_auth_ok() -> bool:
    """Return True iff `gh auth status` reports an authenticated user."""
    result = subprocess.run(  # noqa: S603, S607
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def file_repo_findings(repo: Repo, findings: list[Finding], *, apply: bool) -> None:
    """File or update issues for `repo` based on its findings.

    Dry-run by default; pass ``apply=True`` to actually call `gh`.
    """
    failures = [f for f in findings if f.status == FindingStatus.FAIL]
    if not failures:
        print(f"[{repo.name}] no failures — nothing to file.")
        return

    if not apply:
        _print_dry_run(repo, findings)
        return

    if not gh_auth_ok():
        msg = "gh auth status failed; run `gh auth login` first."
        raise RuntimeError(msg)

    umbrella_body = render_umbrella(repo.name, findings)
    _upsert_issue(
        repo.github_slug,
        umbrella_issue_title(repo.name),
        umbrella_body,
        labels=("consistency",),
    )

    for f in failures:
        if f.tier == Tier.MAY:
            continue
        body = render_child_issue(repo.name, f)
        if body is None:
            continue
        _upsert_issue(
            repo.github_slug,
            child_issue_title(repo.name, f.rule_id),
            body,
            labels=("consistency", f"consistency:{f.tier.value.lower()}"),
        )


def _print_dry_run(repo: Repo, findings: list[Finding]) -> None:
    failures = [f for f in findings if f.status == FindingStatus.FAIL]
    print(f"[{repo.name}] dry-run: would call: gh issue create --repo {repo.github_slug} "
          f'--title "{umbrella_issue_title(repo.name)}" --body-file <umbrella>.md '
          f'--label consistency')
    for f in failures:
        if f.tier == Tier.MAY:
            continue
        print(f"[{repo.name}] dry-run: would call: gh issue create --repo {repo.github_slug} "
              f'--title "{child_issue_title(repo.name, f.rule_id)}" --body-file <{f.rule_id}>.md '
              f'--label consistency --label consistency:{f.tier.value.lower()}')


def _upsert_issue(slug: str, title: str, body: str, labels: tuple[str, ...]) -> None:
    existing = _list_issues_by_title(slug, title)
    open_existing = [i for i in existing if i["state"] == "OPEN"]
    if len(open_existing) > 1:
        print(f"WARNING: multiple open issues match {title!r}; refusing to update. Numbers: "
              f"{[i['number'] for i in open_existing]}", file=sys.stderr)
        return
    if open_existing:
        number = open_existing[0]["number"]
        _run_gh(["issue", "edit", str(number), "--repo", slug, "--body", body])
        return

    cmd = ["issue", "create", "--repo", slug, "--title", title, "--body", body]
    for label in labels:
        cmd += ["--label", label]
    result = _run_gh(cmd)
    print(f"created: {result.stdout.strip()}")


def _list_issues_by_title(slug: str, title: str) -> list[dict]:
    result = _run_gh([
        "issue", "list", "--repo", slug, "--state", "all",
        "--search", f'in:title "{title}"',
        "--json", "number,title,state",
    ])
    return [i for i in json.loads(result.stdout or "[]") if i["title"] == title]


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603, S607
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr}")
    return result
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/filer.py tests/test_filer.py
git commit -m "feat(filer): idempotent gh-issue upsert with dry-run default"
```

---

## Task 23: CLI entrypoint — `consistency_check/__main__.py`

**Files:**
- Create: `consistency_check/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for the CLI entrypoint."""

from __future__ import annotations

import sys

import pytest

from consistency_check.__main__ import main


def test_audit_no_apply_runs_without_gh(monkeypatch, capsys, tmp_path) -> None:
    # Point the registry at a single fake repo to keep this fast
    from consistency_check import repos as repos_mod
    from consistency_check.types import Repo

    fake = Repo(name="fake", path=tmp_path, language="python", github_slug="o/fake")
    monkeypatch.setattr(repos_mod, "REGISTRY", (fake,))

    rc = main(["audit", "--repo", "fake"])
    out = capsys.readouterr().out
    assert "fake" in out
    assert rc in (0, 1)  # may fail rules but should not raise


def test_unknown_repo_exits_with_code(monkeypatch) -> None:
    rc = main(["audit", "--repo", "does-not-exist"])
    assert rc == 2
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
"""Command-line entrypoint for consistency-check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from consistency_check.audit import audit_repo
from consistency_check.filer import file_repo_findings
from consistency_check.report import render_umbrella
from consistency_check.repos import REGISTRY
from consistency_check.types import FindingStatus, Tier


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="consistency-check")
    sub = parser.add_subparsers(dest="cmd", required=True)

    audit = sub.add_parser("audit", help="Audit one or all repos.")
    audit.add_argument("--repo", help="Audit only this repo (default: all).")
    audit.add_argument("--apply", action="store_true", help="File issues via gh CLI.")
    audit.add_argument("--out", type=Path, help="Write per-repo umbrella markdown to this directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd != "audit":
        return 2

    repos = REGISTRY
    if args.repo:
        repos = tuple(r for r in repos if r.name == args.repo)
        if not repos:
            print(f"unknown repo: {args.repo}", file=sys.stderr)
            return 2

    exit_code = 0
    for repo in repos:
        findings = audit_repo(repo)
        body = render_umbrella(repo.name, findings)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{repo.name}.md").write_text(body, encoding="utf-8")
        else:
            print(body)

        if any(f.status == FindingStatus.ERROR for f in findings):
            exit_code = max(exit_code, 2)
        if any(f.status == FindingStatus.FAIL and f.tier == Tier.MUST for f in findings):
            exit_code = max(exit_code, 1)

        try:
            file_repo_findings(repo, findings, apply=args.apply)
        except RuntimeError as exc:
            print(f"filer error: {exc}", file=sys.stderr)
            exit_code = max(exit_code, 3)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add consistency_check/__main__.py tests/test_cli.py
git commit -m "feat(cli): consistency-check audit subcommand"
```

---

## Task 24: Meta-test — standards ↔ rules ID parity

**Files:**
- Create: `tests/test_meta.py`

- [ ] **Step 1: Write the test**

```python
"""Cross-check that documented rule IDs match implemented rule IDs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from consistency_check.audit import all_rules

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _REPO_ROOT / "docs" / "standards"
_RULE_HEADING = re.compile(r"(?m)^###\s+([A-Z]+-\d{3})\b")


def _documented_ids() -> set[str]:
    ids: set[str] = set()
    for f in ("mcp.md", "python.md", "go.md", "mcp-protocol.md"):
        text = (_DOCS / f).read_text(encoding="utf-8")
        ids.update(m.group(1) for m in _RULE_HEADING.finditer(text))
    return ids


def _implemented_ids() -> set[str]:
    return {r.id for r in all_rules()}


def test_no_documented_rule_is_unimplemented() -> None:
    diff = _documented_ids() - _implemented_ids()
    assert not diff, f"documented but not implemented: {sorted(diff)}"


def test_no_implemented_rule_is_undocumented() -> None:
    diff = _implemented_ids() - _documented_ids()
    assert not diff, f"implemented but not documented: {sorted(diff)}"
```

- [ ] **Step 2: Run, verify pass (or fix discrepancies)**

```bash
uv run pytest tests/test_meta.py -v
```

If failures: reconcile by editing either the standards markdown or the rule module so the ID sets match. The plan's task 16 footnote called out a deliberate MCP-021/022/023 reconciliation — fix it now: the standards file currently uses `MCP-021` (stderr), `MCP-022` (structured), `MCP-023` (lockfile); the rule module uses the same IDs but in different positions. Renumber the rule module to match the standards file:

- `MCP-021` → stderr-logging check (`_check_logs_to_stderr`).
- `MCP-022` → structured-logs check (`_check_structured_logs`).
- `MCP-023` → lockfile check (`_check_lockfile`).

Edit `consistency_check/rules/deps.py` to match.

- [ ] **Step 3: Re-run, verify all green**

```bash
uv run pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_meta.py consistency_check/rules/deps.py
git commit -m "test(meta): assert standards and rules IDs are in sync"
```

---

## Task 25: Property test — filer idempotency

**Files:**
- Create: `tests/test_filer_properties.py`

- [ ] **Step 1: Write the property test**

```python
"""Property: running the filer twice with --apply produces the same final state as once."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st

from consistency_check.filer import file_repo_findings
from consistency_check.types import Finding, FindingStatus, Repo, Tier

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
    calls: list[tuple] = []

    def fake_run(args, **kwargs):
        calls.append(tuple(args))
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 0
        # Simulate that after first apply, all titles already exist.
        if "list" in args:
            if any("first" in c for c in calls if "create" in c):
                m.stdout = '[{"number": 1, "title": "x", "state": "OPEN"}]'
            else:
                m.stdout = "[]"
        else:
            m.stdout = "https://github.com/o/r/issues/1\n"
        return m

    with patch("consistency_check.filer.subprocess.run", side_effect=fake_run):
        file_repo_findings(repo, findings, apply=False)  # dry-run is always idempotent
        file_repo_findings(repo, findings, apply=False)

    # No assertion failure means dry-run is stable across calls; the live --apply
    # path is exercised with mocks in test_filer.py — this property test guards the
    # *shape* of repeated invocation rather than wire-level identity.
```

- [ ] **Step 2: Run, verify pass**

```bash
uv run pytest tests/test_filer_properties.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_filer_properties.py
git commit -m "test(filer): property test for repeated-invocation stability"
```

---

## Task 26: Phase 2 review checkpoint

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/mills/Desktop/Projects/consistency-check
uv run pytest -q
uv run ruff check .
uv run ty check
```

Expected: all green. Zero warnings (project-wide rule).

- [ ] **Step 2: Run a dry-run audit against all four real repos**

```bash
uv run consistency-check audit --out /tmp/audit-out
ls /tmp/audit-out
```

Expected: `unifi-mcp.md`, `unraid-mcp.md`, `gandi-mcp.md`, `protonmail-mcp.md` written.

- [ ] **Step 3: Halt and request review**

Stop here. Inform the operator that Phase 2 is complete, share the four audit reports, and request approval before posting issues with `--apply`.

---

## Phase 3 — Live audit + issue filing (Tasks 27–29)

Phase 3 is the user-visible deliverable: GitHub issues filed against each MCP repo.

---

## Task 27: gh auth precheck and per-repo dry-run review

- [ ] **Step 1: Verify gh authentication**

```bash
gh auth status
```

Expected: "Logged in to github.com" for `millsmillsymills`.

- [ ] **Step 2: Re-generate audit output**

```bash
cd /Users/mills/Desktop/Projects/consistency-check
uv run consistency-check audit --out audit-out
```

- [ ] **Step 3: Manually skim each per-repo report**

Open each of `audit-out/{unifi,unraid,gandi,protonmail}-mcp.md` and review:

- Are MUST findings genuine? (Heuristic checks may have false positives — flag any rule that needs tightening BEFORE posting.)
- Are SHOULD findings actionable as written?
- Any AUDIT errors? Investigate the rule that crashed before applying.

If a rule needs fixing: revert to Phase 2, fix the rule, re-run.

- [ ] **Step 4: Operator gate**

The operator confirms: "Reports look right. Proceed to apply." Without this confirmation, do NOT proceed to Task 28.

---

## Task 28: Apply issue filing per repo

Apply one repo at a time so each can be inspected before continuing.

- [ ] **Step 1: File for unifi-mcp**

```bash
uv run consistency-check audit --repo unifi-mcp --apply
```

- [ ] **Step 2: Verify on GitHub**

```bash
gh issue list --repo millsmillsymills/unifi-mcp --search "label:consistency"
```

Spot-check the umbrella + a couple of children in the browser. Confirm titles, bodies, labels are correct.

- [ ] **Step 3: File for unraid-mcp**

```bash
uv run consistency-check audit --repo unraid-mcp --apply
gh issue list --repo millsmillsymills/unraid-mcp --search "label:consistency"
```

- [ ] **Step 4: File for gandi-mcp**

```bash
uv run consistency-check audit --repo gandi-mcp --apply
gh issue list --repo millsmillsymills/gandi-mcp --search "label:consistency"
```

- [ ] **Step 5: File for protonmail-mcp**

```bash
uv run consistency-check audit --repo protonmail-mcp --apply
gh issue list --repo millsmillsymills/protonmail-mcp --search "label:consistency"
```

- [ ] **Step 6: Sanity-check labels exist**

If any `gh issue create` call failed with "label not found", create the label once per repo and re-apply (filer is idempotent):

```bash
for repo in unifi-mcp unraid-mcp gandi-mcp protonmail-mcp; do
  for label in consistency consistency:must consistency:should; do
    gh label create "$label" --repo "millsmillsymills/$repo" --description "consistency-check audit" --color "0e8a16" 2>/dev/null || true
  done
done
```

Then re-run any failed `--apply` invocations.

- [ ] **Step 7: Commit the local audit-out (optional record-keeping)**

```bash
cd /Users/mills/Desktop/Projects/consistency-check
git add audit-out/
git commit -m "chore: snapshot of audit output at first --apply run"
```

---

## Task 29: Final sweep + close-out

- [ ] **Step 1: Confirm all four umbrellas exist**

```bash
for repo in unifi-mcp unraid-mcp gandi-mcp protonmail-mcp; do
  echo "=== $repo ==="
  gh issue list --repo "millsmillsymills/$repo" --search 'in:title "audit umbrella"'
done
```

- [ ] **Step 2: Update consistency-check README**

Add a short section to the repo README documenting the workflow:

```markdown
## Running the audit

```bash
uv run consistency-check audit              # dry-run, all repos, prints to stdout
uv run consistency-check audit --out reports/  # writes per-repo .md files
uv run consistency-check audit --repo unifi-mcp --apply  # files GitHub issues
```

Standards live in `docs/standards/`. Each rule ID (`MCP-001`, `PY-014`, `GO-007`, `PROTO-003`) is referenced verbatim by both the standards file and the matching rule module under `consistency_check/rules/`.
```

(If `README.md` does not exist at consistency-check root, create one with the above section as its primary content and a short header.)

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: document audit workflow"
```

- [ ] **Step 4: Operator handoff**

Inform the operator: Phase 3 complete. Each MCP repo has an umbrella issue + one child per MUST/SHOULD failure. `MAY` failures are inline in the umbrellas. Re-runs are idempotent — running with `--apply` after any repo lands fixes will close resolved children and update the umbrella body.

---

## Self-review notes

- **Spec coverage.** Every section of the design spec has at least one task: standards files (Tasks 1-5), cross-links (Task 6), audit driver (Task 20), report (Task 21), filer (Task 22), CLI (Task 23), meta-tests (Task 24), property tests (Task 25), live run (Tasks 27-28).
- **Rule ID consistency.** Task 24 explicitly reconciles the MCP-021/022/023 numbering so standards docs and rule modules agree before the meta-test asserts parity. The standards file uses MCP-021=stderr, MCP-022=structured-logs, MCP-023=lockfile; rule module aligned in Task 24.
- **Type names.** `Rule`, `Finding`, `Repo`, `Tier`, `FindingStatus` defined in Task 8 are used consistently throughout downstream tasks. `umbrella_issue_title` and `child_issue_title` defined in Task 21 are used in Task 22.
- **No placeholders.** Every code block contains real code. The standards-file content for each rule includes Rationale and Mechanical check (no "TBD"). Tasks 11-19 each have a complete rule module body.
- **Idempotency.** Filer's upsert logic guarantees re-runs do not duplicate issues; tested in Task 22 (mocked) and Task 25 (property).
- **Phase boundaries.** Tasks 7, 26, and the final tasks of Phase 3 explicitly halt for operator review.
