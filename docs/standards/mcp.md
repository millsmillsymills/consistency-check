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

**Mechanical check.** For each direct dep, latest released version is within 12 months of the manifest pin OR an inline comment in the manifest explains why. Requires network access to the package index; reported **n/a** in offline audits rather than a pass.

### MCP-025 — CI enforces a coverage threshold [SHOULD]

**Rationale.** A test suite with no coverage floor silently rots: new code lands untested and the suite still goes green. A gate makes the regression visible at PR time rather than in production.

**Mechanical check.** A workflow file or `pyproject.toml` references a coverage-floor token: `--cov-fail-under` / `fail_under` (Python) or a Go coverage-gate (`go-test-coverage` or a `threshold-total`/`threshold-file`/`threshold-package` check). A bare `-coverprofile` / `-covermode` only emits a report and does not satisfy the gate.

### MCP-026 — CI runs a dependency vulnerability scan [MUST]

**Rationale.** Dependencies are the largest attack surface in a small server. Dependabot (MCP-016) opens upgrade PRs but does not fail the build on a known-vulnerable pin; an explicit scan does, catching CVEs before merge.

**Mechanical check.** A workflow file runs a vulnerability scanner: `pip-audit` (Python), `govulncheck` (Go), GitHub's `dependency-review` action, or a general scanner (`osv-scanner` / `trivy` / `grype` / `snyk`, or a `safety check` invoked in a `run:` step). `safety check` is only counted inside a `run:` command, not in prose or comments.
