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
| `stages.md`      | Maturity ladder `S0`-`S4`: the `min_stage` map, SCOPE.md format, meta-rules |
| `deployment.md`  | Deployment archetypes: remote-hostable / site-local / host-local            |

## Rule IDs

Rules are identified by prefix:

| Prefix         | File             |
| -------------- | ---------------- |
| `MCP-*`        | `mcp.md`         |
| `PY-*`         | `python.md`      |
| `GO-*`         | `go.md`          |
| `PROTO-*`      | `mcp-protocol.md`|
| `MCP-DEPLOY-*` | `deployment.md`  |
| `MCP-STAGE-*`  | `stages.md`      |

The audit tool (`consistency_check/rules/`) references these IDs verbatim. Adding a rule means editing both the standards file and the matching rules module.

## How the audit uses these standards

`uv run consistency-check audit` walks each target MCP repo, runs each rule's mechanical check, and emits a markdown gap report. With `--apply`, it files GitHub issues per the umbrella+children model:

- Per repo: one umbrella issue listing all findings, with `MAY` failures inline.
- Per `MUST` or `SHOULD` failure: one child issue, linked from the umbrella.

Rules are filtered by the repo's declared maturity stage and deployment archetype (both
read from the README `## Status` section) before they run — see `stages.md` and
`deployment.md`. Rules above the declared stage, or scoped to a different archetype, are
reported `n/a`. The report's promotion checklist lists the outstanding rules of the next
stage up, not every `n/a` rule.
