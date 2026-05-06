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
