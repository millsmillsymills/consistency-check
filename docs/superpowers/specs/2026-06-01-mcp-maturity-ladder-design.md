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
What it lacks is a shared notion of **how complete** a server is: a maturity
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
| **Stage** (new) | How complete is the build? | this doctrine + consistency-check | S0-S4 |
| **Compliance** (exists) | How correct vs. standards? | consistency-check | MUST/SHOULD pass rate |
| **Release** (exists) | What's shipped to users? | repo semver / CHANGELOG | `vN` |

The new ladder is the **Stage** axis. It deliberately does **not** reuse
`v1/v2/v3`, for two reasons:

- `vN` is reserved for semver releases (the Release axis).
- `unifi-mcp` already uses "v1 runbook prompts" to mean its first prompts
  increment; reusing `v1` for "docs-first" would collide.

Stages are therefore named **S0** through **S4**.

## The ladder

Each stage is defined by: its definition, the artifacts it requires, the
promotion gate to the next stage, and which `consistency-check` rules apply at
that stage.

The per-stage rule citations below are **illustrative**, not exhaustive. The
authoritative `min_stage` assignment for all 43 rules (MCP-001 through MCP-026,
PROTO-001 through PROTO-017) lives in `stages.md` and must cover every rule. Two
default rules close the map so no rule is left untagged:

- Any rule not explicitly assigned a lower stage defaults to `min_stage = S3`. It
  binds when a server claims completeness, which is the conservative default for
  a correctness rule whose stage is otherwise unstated.
- Deployment- and release-oriented rules (release pipeline, versioned artifacts,
  deployment manifest) are `min_stage = S4`.

The explicit lower-stage assignments are exactly those named per stage below (S0
through S2); every other rule falls to the S3 or S4 default.

### Gate vocabulary

A **gate** is a predicate over a repo's rules and runtime, evaluated to decide
promotion to the next stage. Gates are stated against `min_stage`, never against
"tier" (in this workspace "tier" means the RFC-2119 MUST/SHOULD/MAY axis, a
separate dimension). Each gate clause is marked:

- **(auditor)** when `consistency-check` can check it mechanically.
- **(manual)** when it needs human or agent judgment the auditor cannot perform
  (e.g. running the server, completing a runbook by hand). Manual clauses are
  promotion guidance, not enforced checks.

### S0 - Documented

Docs-first repo, **no `src/`**. The repo *is* the deliverable: it teaches an
agent (or human) to drive the target API/CLI by hand.

**Required artifacts:**
- `README.md` with a `Status` line declaring `S0` (this line is also the
  stage-declaration mechanism; see "Stage declaration" below).
- `SCOPE.md`: target surface + auth model (see "Scope doctrine").
- An endpoint/command map (what operations exist).
- curl recipes (or CLI invocations) for the operations.
- **At least one ordered runbook**: a procedure with commands in execution order
  (e.g. "create a WLAN via the UniFi API, in order").

**Gate to S1:** an agent can complete every runbook by hand using only the repo
contents, with no external knowledge of the API required **(manual)**.

**Rules that apply:** the repo/file/security MUSTs that bind regardless of code:
MCP-001 (top-level files, which also requires `LICENSE`, `CLAUDE.md`, and
`SECURITY.md`, not just the artifacts listed above), MCP-002 (LICENSE/SPDX),
MCP-005/006 (no build artifacts, `.gitignore`), MCP-007 (README sections),
MCP-009 (CLAUDE.md references standards), MCP-019 (no committed secrets),
MCP-020 (SECURITY.md disclosure path), plus MCP-010 (`docs/` exists, SHOULD,
trivially met by a docs-first repo). PROTO-* tool rules and the test/CI/logging
MUSTs (MCP-011/014/021 and the like) are **N/A at S0**: a docs-only repo must not
be dinged for "no tools," "no tests," or "no server."

### S1 - Walking skeleton

The server scaffolds and runs. **Read-only tools only.** stdio transport. Unit
tests on recorded cassettes/fixtures.

**Gate to S2:** server starts and `list_tools` is non-empty **(manual)**; read
tools pass cassette tests **(manual)**; logs go to stderr **(auditor: MCP-021)**.

**Adds rules:** PROTO-001/002/003/004 (tool naming, typed schema, docstrings),
MCP-021/022 (structured logging to stderr).

### S2 - Wrapped

Read **and** write tools. Writes env-gated, default-off. Full unit coverage. CI
runs lint+test on push and PR, green. Lockfile committed.

**Gate to S3:** every MUST-tier rule with `min_stage` at or below S2 passes in
`consistency-check` **(auditor)**.

**Adds rules:** PROTO-005/006 (read/write separation, write-gating),
MCP-014/017/023 (CI present, `uses:` pinned to 40-char SHA + version comment,
lockfile committed).

### S3 - Complete

**Full surface parity** with the declared scope. Live integration tests against a
real instance. Runbooks **promoted** from S0 curl-markdown to MCP **prompts**
(the existing `unifi-mcp` pattern). All SHOULDs satisfied.

**Gate to S4:** every rule at every tier with `min_stage` at or below S3 passes
**(auditor)**; live integration tests pass **(manual)**.

### S4 - Distributed

A deployment model is wired (MCPB / remote HTTP / PyPI) plus a release pipeline
and versioned `vN` releases. This is where the `build-mcp-server` deployment-model
decision is made, after tools exist rather than before.

## Scope doctrine

`SCOPE.md` is written at S0 and declares the target surface and auth model.

**Default presumption: total coverage.** S3 ("Complete") means the *whole*
API/CLI surface is wrapped. Partial coverage means "not yet S3," not "done."

A server may declare a **scoped-complete exception**: an explicit, logged
stopping point in `SCOPE.md`. Absent that declaration, the auditor treats missing
surface as a blocker to S3, not as completion.

### SCOPE.md format

`SCOPE.md` uses H2 sections the auditor can parse mechanically:

- `## Surface`: a bullet list, one declared operation per line. This is the
  target surface the S3 coverage check measures wrapped tools against.
- `## Auth`: the auth model, in prose.
- `## Scope exception` *(optional)*: present only for a scoped-complete
  exception. Its body states what is out of scope and why (e.g. "WLAN + VLAN
  operations only; remainder out of scope, see rationale below"). The auditor
  keys off the heading's presence.

The S3 total-coverage check compares wrapped tools against the `## Surface` list.
A repo carrying a `## Scope exception` heading is held to its declared subset, not
the full surface.

## Runbook lifecycle

A runbook is one operational procedure, **promoted in form** as the repo climbs.
Same content, richer substrate:

- **S0:** markdown + curl/CLI commands, executed by hand.
- **S3:** an MCP **prompt** that names the real tools to call, in order (exactly
  `unifi-mcp`'s current pattern).

This resolves the naming collision: `unifi-mcp`'s "v1 runbook prompts" are the
**S3 form** of runbooks that, under this doctrine, would have begun as S0 curl
docs.

## Stage declaration

A repo declares its stage inside the **`## Status` section already required by
MCP-007** in `README.md` (e.g. a `Status: S2` line under that heading). No new
metadata file is introduced, keeping a single source of truth. Note MCP-007 today
only checks that the `## Status` heading *exists*; it does not read the section
body. This design adds the token-parsing step (extract an `S`-token from the
section) as net-new auditor work.

The accepted token set is `S0` through `S4`. A repo whose `## Status` section
carries a release/maturity word but no `S`-token is treated as **unstaged**, and
the auditor emits a warning rather than guessing. Verified against the current
suite: all six servers use prose Status lines ("v1.", "Feature-complete", "Under
active development") with no `S`-token, so on rollout every existing repo parses
as unstaged until its README is annotated. That is the intended, non-crashing
default.

## consistency-check integration

- Each rule gains a **`min_stage`** tag (`S0` through `S4`).
- The auditor reads the repo's declared stage from the README `## Status` section.
- It evaluates only rules whose `min_stage` is at or below the declared stage,
  and **separately** reports "next-gate" rules (those at `declared stage + 1`) as
  the explicit promotion checklist.
- Report shape becomes, e.g.:
  *"unraid-mcp: declared S3, compliant through S3 gates, 2 SHOULDs pending; S4
  needs a release pipeline."*

The rubric definition (this ladder, the per-rule `min_stage` assignments) is the
source of truth and lives in `consistency-check/docs/standards/stages.md`,
alongside `mcp.md`.

### Warnings and the Finding model

The auditor's existing outcomes are `pass`/`fail`/`n/a`/`error`, with exit codes
0 (pass, or MAY-only failures), 1 (at least one MUST fails), 2 (unknown repo or a
check raised), 3 (filer error). Stage warnings reuse this model rather than adding
a new outcome class: each is a `fail` Finding on a MAY-tier meta-rule:

- **MCP-STAGE-DECL** fires when the `## Status` section carries no `S`-token
  (unstaged).
- **MCP-STAGE-DRIFT** fires when a declared stage contradicts the cheap signals
  in the drift table (see "Risks").

Because both are MAY-tier, they surface in the report without setting exit 1, so a
warning never fails an otherwise-clean audit.

## build-mcp-server integration

A new **Phase 0** is inserted before the existing deployment-model questions:

- Scaffold at **S0 docs-first**: create the repo, write `SCOPE.md` and the first
  runbook, no `src/`.
- The current Phase 2 (deployment-model selection: remote HTTP / MCPB / stdio)
  moves to the **S3 to S4** transition, where it belongs.

The skill's `SKILL.md` references `stages.md` so the on-ramp and the rubric stay
in lockstep.

## Where the doctrine lives

| Concern | Location |
|---|---|
| Rubric source of truth (ladder + `min_stage` map) | `consistency-check/docs/standards/stages.md` |
| Doctrine pointer / shared vocabulary | workspace `CLAUDE.md` (to `mcp-server-dev-defaults/CLAUDE.md`) |
| Forward on-ramp | `build-mcp-server` `SKILL.md` Phase 0 |

## Non-goals

- Retrofitting existing servers down to S0 (they are graded where they sit).
- A second metadata file for stage declaration (README `Status` is reused).
- Automating runbook promotion (curl to prompt is a manual authoring step).
- The two-axis (stage by coverage %) model, rejected in favor of a single ladder
  with total-coverage-default scope semantics.

## Risks

- **Stage drift.** A declared `Status` can lag real state. The auditor
  cross-checks cheap per-stage signals and emits the MCP-STAGE-DRIFT warning on
  mismatch:

  | Declared | Drift signal (warns if true) |
  |---|---|
  | S0 | a `src/` tree exists |
  | S1 or higher | no `src/` tree, or the `list_tools` source defines zero tools |
  | S2 or higher | write tools exist with no env-gate, or no CI workflow present |
  | S3 or higher | no integration-test marker, or runbooks still curl-only (no MCP prompts) |
  | S4 | no release pipeline or deployment manifest |

  These are cheap static signals, not a full re-audit; they catch the obvious
  contradictions.
- **min_stage bikeshedding.** Assigning every existing rule a `min_stage` is a
  one-time judgment call; the assignments in this spec are the starting point and
  may shift as the first new server climbs the ladder.
