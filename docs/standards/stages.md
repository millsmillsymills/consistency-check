# MCP Server Maturity Stages (`S0`–`S4`)

The **stage** axis records how complete an MCP server is. It is orthogonal to the
RFC-2119 **tier** axis (MUST/SHOULD/MAY) and to the **release** axis (semver `vN`).
A repo declares its stage with an `S0`–`S4` token in its README `## Status`
section; the auditor evaluates only rules whose `min_stage` is at or below the
declared stage and reports the next stage's rules as a promotion checklist.

See `docs/superpowers/specs/2026-06-01-mcp-maturity-ladder-design.md` for the
full design rationale.

## The ladder

- **S0 Documented** — docs-first repo, no `src/`. README, SCOPE.md, endpoint map,
  curl recipes, and at least one ordered runbook. Teaches an agent to drive the
  API by hand.
- **S1 Walking skeleton** — server runs; read-only tools; stdio; unit tests on
  cassettes.
- **S2 Wrapped** — read and write tools; writes env-gated default-off; CI green;
  lockfile committed.
- **S3 Complete** — full surface parity with the declared scope; live integration
  tests; runbooks promoted to MCP prompts; SHOULDs satisfied.
- **S4 Distributed** — deployment model wired plus a release pipeline and
  versioned releases.

## min_stage map

Closure rule: any rule not listed here defaults to `min_stage = S3`;
deployment/release rules are `S4`.

| min_stage | Rules |
|---|---|
| S0 | MCP-001, MCP-002, MCP-005, MCP-006, MCP-007, MCP-009, MCP-010, MCP-019, MCP-020 |
| S1 | PROTO-001, PROTO-002, PROTO-003, PROTO-004, MCP-021, MCP-022 |
| S2 | PROTO-005, PROTO-006, MCP-014, MCP-017, MCP-023 |
| S3 | *(all rules not otherwise listed)* |
| S4 | MCP-018 |

## SCOPE.md format

`SCOPE.md` is written at S0 and parsed by the auditor:

- `## Surface` — one declared operation per bullet; the S3 coverage check measures
  wrapped tools against this list.
- `## Auth` — the auth model, in prose.
- `## Scope exception` *(optional)* — present only for a deliberate
  scoped-complete stop. Its presence holds the repo to its declared subset rather
  than the full surface.

## Stage declaration

A repo declares its stage inside the `## Status` section already required by
MCP-007 (e.g. a line `Stage: S2`). The accepted token set is `S0`–`S4`. A repo
whose `## Status` section carries no `S`-token is **unstaged**: the auditor runs
every rule (no stage filtering) and emits the MCP-STAGE-DECL warning.
