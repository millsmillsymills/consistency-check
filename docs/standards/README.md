# MCP Server Standards

Canonical standards for the millsymills-com MCP suite. Authoritative source of truth.

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
