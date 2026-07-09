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

**Mechanical check.** Python: every `@mcp.tool`-decorated function has fully type-annotated parameters (no bare `Any` for top-level args). Go: not mechanically enforced — reported **n/a**; typed schemas verified by manual review.

### PROTO-004 — Each tool has Args / Returns / Raises docstring [MUST]

**Rationale.** Description is surfaced to the model and to humans browsing the tool list.

**Mechanical check.** Python: function docstring includes `Args:` and either `Returns:` or `Yields:`. Go: not mechanically enforced — reported **n/a**; the `Description` field is verified by manual review.

### PROTO-005 — Read tools and write tools are separated [SHOULD]

**Rationale.** Lets clients gate destructive ops independently.

**Mechanical check.** Source contains either (a) two separate registration functions/maps named for read vs write, or (b) a runtime gate (e.g. `if ENABLE_WRITES:` / `if cfg.AllowWrites` / `if config.writes_enabled:`) around every state-changing tool registration.

### PROTO-006 — Write tools require explicit env-flag opt-in [MUST]

**Rationale.** Default-safe posture: a misconfigured server cannot mutate state.

**Mechanical check.** Each write tool's registration is wrapped by a configuration boolean read from env (e.g. `UNRAID_ENABLE_WRITE_TOOLS=true`).

## Capabilities and transport

### PROTO-007 — Server registers capabilities explicitly [MUST]

**Mechanical check.** Server constructor passes a non-default capabilities object enumerating tools (and prompts/resources if used).

### PROTO-008 — Default transport is stdio; SSE/HTTP behind explicit flag [MUST]

**Rationale.** stdio is the lowest-friction transport for desktop clients and the project default.

**Mechanical check.** Go: a `cmd/.../main.go` entrypoint is present (stdio is the SDK default; a forced non-stdio default is caught by PROTO-017). Python: not mechanically checkable from source — reported **n/a**; the stdio default is verified by manual review.

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

**Mechanical check.** No log statement formats a variable whose name matches the regex above. Auditor inspects all `logger.*` / `log.*` call sites, stripping string-literal contents first so human-readable text inside the format string (e.g. `"...capture the API key."`) does not produce false positives.

## Transport and runtime safety

### PROTO-013 — stdout reserved for JSON-RPC [MUST]

**Rationale.** Under the stdio transport, stdout carries the JSON-RPC frame stream. Any stray byte written to stdout corrupts the protocol and disconnects the host.

**Mechanical check.** Source contains no stdout write. Python: no `print(...)` call without `file=` routing it elsewhere. Go: no `fmt.Print`/`Printf`/`Println` and no `os.Stdout` write. Diagnostics go to stderr (see MCP-021).

### PROTO-014 — Outbound HTTP clients set an explicit timeout [MUST]

**Rationale.** A client with no timeout can hang indefinitely and stall the host waiting on the tool. Go's `http.Client` has no default timeout; an explicit one is mandatory and is required everywhere for clarity.

**Mechanical check.** Every HTTP client construction sets a timeout. Python: `httpx.Client(...)` / `httpx.AsyncClient(...)` includes a `timeout=` argument. Go: `http.Client{...}` includes a `Timeout:` field.

### PROTO-015 — Each tool has a description summary [MUST]

**Rationale.** The host model selects tools from their description. A tool with typed Args but no summary line (see PROTO-004) ships blind to the model.

**Mechanical check.** Python: each `@mcp.tool` function either passes `description=` to the decorator or opens with a docstring whose first non-empty line is a summary (not an `Args:`/`Returns:` section header). Go: not mechanically enforced — reported **n/a**.

### PROTO-016 — Tools declare MCP annotations [SHOULD]

**Rationale.** MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) let a host gate or auto-approve calls — read-only tools can run unattended, destructive ones can demand confirmation. Without them the client must treat every tool as opaque and equally dangerous.

**Mechanical check.** A repo that defines at least one tool also references a tool-annotation marker somewhere in its source: one of `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` (or their snake_case forms) or a `ToolAnnotations` constructor. A server that exposes no tools passes vacuously.

### PROTO-017 — HTTP/SSE transport requires auth and a loopback guard [MUST]

**Rationale.** PROTO-008 keeps stdio the default and puts HTTP/SSE behind a flag, but once a network transport is enabled the server is reachable by other processes and, via DNS rebinding, by web pages. The MCP spec requires local HTTP servers to authenticate requests and to validate the `Origin`/`Host` header (or bind to loopback) so a browser cannot drive the server.

**Mechanical check.** Only fires when the source enables a network transport (an `sse`/`streamable-http`/`http` transport selection, an SSE server/mux/listener, or an `MCP_TRANSPORT` switch). When it does, the source must also show **both** an auth marker (`bearer` / `authorization` / `auth`) **and** a host-guard marker (`127.0.0.1` / `localhost` / `loopback` / `origin`). stdio-only servers pass vacuously.
