# Design: MCP server maturity ladder (doctrine + rubric)

**Date:** 2026-06-01
**Status:** Approved design, pending implementation plan
**Scope:** A workspace-wide maturity ladder for MCP server development, defined
once as doctrine and consumed by two systems: the `build-mcp-server` skill (as a
forward on-ramp for new servers) and `consistency-check` (as a grading rubric for
existing servers).

## Problem

The workspace has six MCP servers, all already near-complete, and a
`consistency-check` auditor that grades each against RFC-2119 MUST/SHOULD tiers.
What it lacks is a shared notion of **how complete** a server is — a maturity
progression from "no server yet, just docs teaching Claude to drive the API via
curl" up through "full parity with live tests and runbooks" to "distributed."

Two problems follow:

1. **No on-ramp for new servers.** `build-mcp-server` jumps straight to
   deployment-model selection and tool scaffolding. There is no sanctioned
   "start with docs, climb to code" path, even though that is how a careful
   integration should begin.
2. **The audit can't express partial progress.** A docs-only repo with no tools
   would fail PROTO-* tool rules, even though "no tools yet" is the *correct*
   state for an early-stage server. Compliance and completeness are conflated.

## Three orthogonal axes

The core framing: "how complete," "how correct," and "what's shipped" are
independent and must not be conflated.

| Axis | Question | Lives in | Values |
|---|---|---|---|
| **Stage** (new) | How complete is the build? | this doctrine + consistency-check | S0–S4 |
| **Compliance** (exists) | How correct vs. standards? | consistency-check | MUST/SHOULD pass rate |
| **Release** (exists) | What's shipped to users? | repo semver / CHANGELOG | `vN` |

The new ladder is the **Stage** axis. It deliberately does **not** reuse
`v1/v2/v3`, for two reasons:

- `vN` is reserved for semver releases (the Release axis).
- `unifi-mcp` already uses "v1 runbook prompts" to mean its first prompts
  increment; reusing `v1` for "docs-first" would collide.

Stages are therefore named **S0–S4**.

## The ladder

Each rung is defined by: its definition, the artifacts it requires, the
promotion gate to the next rung, and which `consistency-check` rules apply at
that rung.

The per-rung rule citations below are **illustrative**, not exhaustive. The
authoritative `min_stage` assignment for all 43 rules (MCP-001–026,
PROTO-001–017) is produced during implementation and lives in `stages.md`; it
must cover every rule, not just the representative ones named here.

### S0 — Documented

Docs-first repo, **no `src/`**. The repo *is* the deliverable: it teaches an
agent (or human) to drive the target API/CLI by hand.

**Required artifacts:**
- `README.md` with a `Status` line declaring `S0` (this line is also the
  stage-declaration mechanism — see "Stage declaration" below).
- `SCOPE.md` — target surface + auth model (see "Scope doctrine").
- An endpoint/command map (what operations exist).
- curl recipes (or CLI invocations) for the operations.
- **≥1 ordered runbook** — a procedure with commands in execution order
  (e.g. "create a WLAN via the UniFi API, in order").

**Gate to S1:** an agent can complete every runbook by hand using only the repo
contents — no external knowledge of the API required.

**Rules that apply:** the repo/file/security MUSTs that bind regardless of code —
MCP-001 (top-level files, which also requires `LICENSE`, `CLAUDE.md`, and
`SECURITY.md`, not just the artifacts listed above), MCP-002 (LICENSE/SPDX),
MCP-005/006 (no build artifacts, `.gitignore`), MCP-007 (README sections),
MCP-009 (CLAUDE.md references standards), MCP-019 (no committed secrets),
MCP-020 (SECURITY.md disclosure path) — plus MCP-010 (`docs/` exists, SHOULD,
trivially met by a docs-first repo). PROTO-* tool rules and the test/CI/logging
MUSTs (MCP-011/014/021…) are **N/A at S0** — a docs-only repo must not be dinged
for "no tools," "no tests," or "no server."

### S1 — Walking skeleton

The server scaffolds and runs. **Read-only tools only.** stdio transport. Unit
tests on recorded cassettes/fixtures.

**Gate to S2:** server starts; `list_tools` is non-empty; read tools pass
cassette tests; logs go to stderr.

**Adds rules:** PROTO-001/002/003/004 (tool naming, typed schema, docstrings),
MCP-021/022 (structured logging to stderr).

### S2 — Wrapped

Read **and** write tools. Writes env-gated, default-off. Full unit coverage. CI
runs lint+test on push and PR, green. Lockfile committed.

**Gate to S3:** all S2-tier MUSTs pass in `consistency-check`.

**Adds rules:** PROTO-005/006 (read/write separation, write-gating),
MCP-014/017/023 (CI present, `uses:` pinned to 40-char SHA + version comment,
lockfile committed).

### S3 — Complete

**Full surface parity** with the declared scope. Live integration tests against a
real instance. Runbooks **promoted** from S0 curl-markdown to MCP **prompts**
(the existing `unifi-mcp` pattern). All SHOULDs satisfied.

**Gate to S4:** clean audit at every tier + live integration tests pass.

### S4 — Distributed

A deployment model is wired (MCPB / remote HTTP / PyPI) plus a release pipeline
and versioned `vN` releases. This is where the `build-mcp-server` deployment-model
decision is actually made — not before a single tool exists.

## Scope doctrine

`SCOPE.md` is written at S0 and declares the target surface and auth model.

**Default presumption: total coverage.** S3 ("Complete") means the *whole*
API/CLI surface is wrapped. Partial coverage means "not yet S3," not "done."

A server may declare a **scoped-complete exception**: an explicit, logged
stopping point in `SCOPE.md` (e.g. "WLAN + VLAN operations only; remainder out of
scope, see §rationale"). Absent that declaration, the auditor treats missing
surface as a blocker to S3, not as completion.

## Runbook lifecycle

A runbook is one operational procedure that is **promoted in form** as the repo
climbs — same content, richer substrate:

- **S0:** markdown + curl/CLI commands, executed by hand.
- **S3:** an MCP **prompt** that names the real tools to call, in order (exactly
  `unifi-mcp`'s current pattern).

This resolves the naming collision: `unifi-mcp`'s "v1 runbook prompts" are the
**S3 form** of runbooks that, under this doctrine, would have begun as S0 curl
docs.

## Stage declaration

A repo declares its stage inside the **`## Status` section already required by
MCP-007** in `README.md` (e.g. a `Status: S2` line under that heading). No new
metadata file is introduced — single source of truth. Note MCP-007 today only
checks that the `## Status` heading *exists*; it does not read the section body.
This design adds the token-parsing step (extract an `S`-token from the section)
as net-new auditor work.

The accepted token set is `S0`–`S4`. A repo whose `## Status` section carries a
release/maturity word but no `S`-token is treated as **unstaged** and the auditor
emits a warning rather than guessing. Verified against the current suite: all six
servers use prose Status lines ("v1.", "Feature-complete", "Under active
development") with no `S`-token, so on rollout every existing repo parses as
unstaged until its README is annotated — the intended, non-crashing default.

## consistency-check integration

- Each rule gains a **`min_stage`** tag (`S0`–`S4`).
- The auditor reads the repo's declared stage from the README `## Status` section.
- It evaluates only rules whose `min_stage ≤ declared stage`, and **separately**
  reports "next-gate" rules — those at `declared stage + 1` — as the explicit
  promotion checklist.
- Report shape becomes, e.g.:
  *"unraid-mcp — declared S3, compliant through S3 gates, 2 SHOULDs pending; S4
  needs a release pipeline."*

The rubric definition (this ladder, the per-rule `min_stage` assignments) is the
source of truth and lives in `consistency-check/docs/standards/stages.md`,
alongside `mcp.md`.

## build-mcp-server integration

A new **Phase 0** is inserted before the existing deployment-model questions:

- Scaffold at **S0 docs-first**: create the repo, write `SCOPE.md` and the first
  runbook, no `src/`.
- The current Phase 2 (deployment-model selection: remote HTTP / MCPB / stdio)
  moves to the **S3→S4** transition, where it belongs.

The skill's `SKILL.md` references `stages.md` so the on-ramp and the rubric stay
in lockstep.

## Where the doctrine lives

| Concern | Location |
|---|---|
| Rubric source of truth (ladder + `min_stage` map) | `consistency-check/docs/standards/stages.md` |
| Doctrine pointer / shared vocabulary | workspace `CLAUDE.md` (→ `mcp-server-dev-defaults/CLAUDE.md`) |
| Forward on-ramp | `build-mcp-server` `SKILL.md` Phase 0 |

## Non-goals

- Retrofitting existing servers down to S0 (they are graded where they sit).
- A second metadata file for stage declaration (README `Status` is reused).
- Automating runbook promotion (curl→prompt is a manual authoring step).
- The two-axis (stage × coverage %) model — rejected in favor of a single ladder
  with total-coverage-default scope semantics.

## Risks

- **Stage drift.** A repo's declared `Status` can lag its real state. Mitigation:
  the auditor cross-checks cheap signals (e.g. a repo claiming `S0` that has a
  `src/` tree, or claiming `S3` with no integration tests) and warns on
  mismatch.
- **min_stage bikeshedding.** Assigning every existing rule a `min_stage` is a
  one-time judgment call; the assignments in this spec are the starting point and
  may shift as the first new server climbs the ladder.
