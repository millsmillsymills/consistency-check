# MCP Consistency Standards & Audit — Design Spec

- **Date:** 2026-05-06
- **Status:** Approved (brainstorm); awaiting writing-plans handoff
- **Repo:** `consistency-check` (this repo is the source of truth)
- **Targets:** `unifi-mcp`, `unraid-mcp`, `gandi-mcp` (Python/FastMCP); `protonmail-mcp` (Go/mcp-go)

## Goal

Define one canonical set of MCP-server standards that all four MCP repos are graded against, and build a re-runnable auditor that emits a markdown gap report and (optionally) files GitHub issues against each repo for each gap.

## Decisions (brainstorm clarifiers)

| ID  | Decision                                                                                              |
| --- | ----------------------------------------------------------------------------------------------------- |
| Q1  | **Polyglot.** Standards split: language-agnostic core + Python + Go.                                  |
| Q2  | **Hybrid source of truth.** External MCP spec / SDK conventions for protocol items; best-of-current for repo-shape items. |
| Q3  | **Six listed dimensions plus adjacent essentials:** structure, logic, code quality, tests, debugging, docs, security/secrets, CI/release, dependency hygiene, MCP-protocol (tools/capabilities/transport/error codes), observability/logging. **Note on "logic":** the auditor mechanically checks the structural shell that supports good logic (boundary placement, error type hierarchy, lifespan/teardown shape). Substantive logic-correctness review remains a human/agent task and is out of scope for the audit script. |
| Q4  | **Hybrid issue granularity.** Per repo: one umbrella issue. Findings with tier `MUST` or `SHOULD` get a child issue. Findings with tier `MAY` are listed inline in the umbrella body only. This is the precise operational rule referenced from the data-flow section. |
| Q5  | **RFC 2119 tiers** — every standard tagged `MUST` / `SHOULD` / `MAY`. Findings inherit severity from tier. |
| Q6  | **Spec + lightweight repo-scan script.** A Python `consistency_check` package walks each MCP repo and emits a markdown report. |
| Q7  | **Multi-file canonical standards** under `consistency-check/docs/standards/` (`mcp.md`, `python.md`, `go.md`, `mcp-protocol.md`). |
| Q8  | **Script auto-files via `gh` after `--apply` flag.** Default is `--dry-run`; idempotent on issue title. |
| W   | **Three-phase work shape.** Phase 1: standards docs. Phase 2: checker + fixture tests. Phase 3: live audit + issue filing. |
| R   | **Hardcoded rule encoding.** One Python function per rule; no DSL, no plugin loader, no YAML interpreter. |

## Architecture

```
consistency-check/                          (source of truth)
├── docs/
│   ├── standards/
│   │   ├── README.md                       index + how-to-read
│   │   ├── mcp.md                          language-agnostic core
│   │   ├── python.md                       uv/ruff/ty/pytest/FastMCP
│   │   ├── go.md                           golangci-lint/go test/mcp-go
│   │   └── mcp-protocol.md                 tool naming, capabilities, transport, error codes
│   └── superpowers/specs/2026-05-06-mcp-consistency-design.md
├── consistency_check/                      Python package
│   ├── __main__.py                         CLI entrypoint
│   ├── repos.py                            target repo registry
│   ├── rules/                              one module per dimension
│   │   ├── structure.py
│   │   ├── docs.py
│   │   ├── tests.py
│   │   ├── ci.py
│   │   ├── security.py
│   │   ├── deps.py
│   │   ├── mcp_protocol.py
│   │   ├── python.py
│   │   └── go.py
│   ├── report.py                           markdown emitter
│   └── filer.py                            gh CLI integration
├── tests/
│   ├── fixtures/                           good_python/ bad_python/ good_go/ bad_go/
│   └── test_*.py
├── pyproject.toml                          uv, ruff, ty
└── CLAUDE.md
```

**Boundaries.** Rules know nothing about each other. Report knows nothing about gh. Filer knows nothing about rule logic. Standards docs are human-readable; checker references rule IDs verbatim.

## Components

1. **Standards docs (`docs/standards/*.md`)** — every rule has: ID (`MCP-001`, `PY-014`, `GO-007`, `PROTO-003`), tier (MUST/SHOULD/MAY), one-line statement, rationale, mechanical check pattern.
2. **Audit CLI (`consistency_check/__main__.py`)** — `python -m consistency_check audit [--repo NAME] [--apply] [--dry-run] [--out PATH]`. Defaults to dry-run, all repos, stdout report. `--apply` is the only flag that touches GitHub.
3. **Repo registry (`repos.py`)** — single dataclass list: `(name, path, language, github_slug)`. No autodetection.
4. **Rules modules (`rules/*.py`)** — each module exports `RULES: list[Rule]`. A `Rule` is `(id, tier, applies_to, check)` where `applies_to` is a set of languages and `check(repo) -> Finding | None`. Hardcoded.
5. **Report emitter (`report.py`)** — Findings → markdown. Two outputs: per-repo umbrella body + per-finding child issue body. Templates literal, not Jinja.
6. **Filer (`filer.py`)** — wraps `gh issue create/edit`. Idempotent by title prefix `[consistency] <repo>: <rule-id>`. Skips if existing open issue with same title. `--dry-run` prints `gh` invocations; `--apply` runs them.
7. **Fixture repos (`tests/fixtures/`)** — synthetic mini-trees that exercise pass + fail per rule. No real MCP code; trivial placeholder code.

## Data flow

```
                         ┌────────────────┐
                         │ standards/*.md │  human + agent reference
                         └───────┬────────┘
                                 │ rule IDs referenced by check fns
                                 ▼
┌──────────────┐   load   ┌────────────┐   walk   ┌──────────────┐
│ repos.py     │ ───────▶ │ rules/*.py │ ───────▶ │ target repo  │
│ (registry)   │          │  (checks)  │ ◀──read──│  filesystem  │
└──────────────┘          └─────┬──────┘          └──────────────┘
                                │ findings
                                ▼
                         ┌──────────────┐
                         │  report.py   │
                         │ md per repo  │
                         └──────┬───────┘
                                │ findings + bodies
                                ▼
                         ┌──────────────┐
                         │  filer.py    │ ── gh CLI ──▶ GitHub issues
                         │ dry-run/apply│              (umbrella + children)
                         └──────────────┘
```

**Single audit run:**

1. CLI parses args. Defaults: all repos, dry-run.
2. For each repo in registry, load rules whose `applies_to` matches repo language.
3. Run each `check(repo)`. Output: list of `Finding(rule_id, tier, status, evidence)` where `status ∈ {pass, fail, n/a, error}`.
4. `report.py` groups findings per repo → renders umbrella markdown (full table) + per-finding child markdown (only for `fail` where tier ≥ `SHOULD`; `MAY` findings stay inline in umbrella).
5. `filer.py`:
   - **dry-run** (default): write report to stdout/path; print would-be `gh` invocations.
   - **apply**: post umbrella, then children, linking children back to umbrella; update existing umbrella body if title matches.

Steps 1–4 are pure. Side effects only in step 5 with `--apply`.

**Re-runs.** Filer is idempotent on title. Re-running with `--apply` updates the umbrella body in place; closes child issues for now-resolved findings; opens children for new failures.

## Error handling & edge cases

- **Per-rule failure isolation.** A crashing rule emits `Finding(status=error, evidence=<traceback excerpt>)`. Run continues.
- **Missing repo on disk.** Emit one `Finding(status=error, rule_id=REPO-MISSING)`; skip; exit code reflects errors.
- **Language mismatch.** Rule whose `applies_to` excludes the repo language emits `status=n/a`; hidden from umbrella unless `--verbose`.
- **`gh` not installed / not authed.** `--apply` precheck: `gh auth status`. Fail fast with actionable message before any side effect. Dry-run never calls `gh`.
- **Network/GitHub failures during apply.** Per-issue retry with exponential backoff (max 3). On final failure, log unposted markdown to `.consistency-cache/<repo>-<rule>.md` for manual recovery.
- **Idempotency edge cases:**
  - Closed issue with same title → don't reopen; log warning.
  - Multiple open issues with same title → refuse to update; log warning; require manual cleanup.
  - Whitespace-only umbrella body diff → skip update.
- **Concurrent runs.** Out of scope. Single-operator tool. No locking.
- **Exit codes.** `0` clean. `1` MUST failures present. `2` checker errors. `3` filer errors during `--apply`.
- **Stale standards.** Meta-warning if a code rule ID is missing from `docs/standards/`, or a documented rule ID is missing from code. Tested in fixture suite.

## Testing strategy

**Unit tests on rules.** Each rule module has `tests/test_rules_<dim>.py`. Per rule: pass and fail cases against synthetic fixture trees. No mocking — fixtures are real directories on disk.

**Fixture repos.** `good_python/`, `bad_python/`, `good_go/`, `bad_go/`. Skeleton trees that exercise every rule; trivial placeholder code. Goal is filesystem shape, not behavior.

**Report tests.** Snapshot-style: feed a known list of `Finding`s into `report.py`; assert markdown matches a checked-in golden. Update goldens with `pytest --snapshot-update`.

**Filer tests.** Pure dry-run. Mock `subprocess.run` to capture would-be `gh` invocations; assert correct args, idempotency logic. Live `gh` only behind `INTEGRATION=1`, manual.

**Cross-repo consistency test.** Meta-test parses `docs/standards/*.md` for rule IDs and `consistency_check/rules/*.py` for referenced rule IDs; asserts the two sets match.

**Property tests.** Hypothesis generates random Finding lists; asserts running filer twice with `--apply` produces the same final issue state as running once.

**Tools.** `pytest -q`, `ruff`, `ty`. No mypy. uv-managed venv. `prek` hooks. CI runs unit + meta + property tests on every push.

**Out of scope for testing.** Live `gh` posting (manual integration only); rule rationale wording (humans review); the four real MCP repos (audit inputs, not test subjects).

## Phasing (informs writing-plans handoff)

- **Phase 1 — Standards docs.** Commit `docs/standards/{README,mcp,python,go,mcp-protocol}.md`. Reviewable on its own. No code yet.
- **Phase 2 — Checker.** Commit `consistency_check/` package + `tests/fixtures/*` + tests. Pure code review; no live impact. Achieve green tests against fixtures. Run `python -m consistency_check audit --dry-run` against the four real repos to sanity-check output.
- **Phase 3 — Audit + file.** Run with `--apply`. Review filed issues; iterate as needed.

## Open items deferred to writing-plans

- Exact rule list per dimension (`docs/standards/*.md` content). Brainstorm gathered structural facts; specific rules will be enumerated as the writing-plans task proceeds. Initial seed list will be derived from this repo's existing `CLAUDE.md` plus the cross-repo facts captured during exploration.
- Exact `Finding`, `Rule`, `Repo` dataclass field names — a writing-plans concern.
- Whether to add a fifth fixture for a "polyglot" repo — defer; not needed for current four targets.
