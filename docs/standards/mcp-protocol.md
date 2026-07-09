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

**Mechanical check.** Source contains either (a) two separate registration functions/maps named for read vs write, or (b) a runtime gate (e.g. `if ENABLE_WRITES:` / `if cfg.AllowWrites` / `if config.writes_enabled:`) around every state-changing tool registration.

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

**Mechanical check.** Each `@mcp.tool` function either passes `description=` to the decorator or opens with a docstring whose first non-empty line is a summary (not an `Args:`/`Returns:` section header).

### PROTO-016 — Tools declare MCP annotations [SHOULD]

**Rationale.** MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) let a host gate or auto-approve calls — read-only tools can run unattended, destructive ones can demand confirmation. Without them the client must treat every tool as opaque and equally dangerous.

**Mechanical check.** A repo that defines at least one tool also references a tool-annotation marker somewhere in its source: one of `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` (or their snake_case forms) or a `ToolAnnotations` constructor. A server that exposes no tools passes vacuously.

### PROTO-017 — HTTP/SSE transport requires auth and a loopback guard [MUST]

**Rationale.** PROTO-008 keeps stdio the default and puts HTTP/SSE behind a flag, but once a network transport is enabled the server is reachable by other processes and, via DNS rebinding, by web pages. The MCP spec requires local HTTP servers to authenticate requests and to validate the `Origin`/`Host` header (or bind to loopback) so a browser cannot drive the server.

**Mechanical check.** Only fires when the source enables a network transport (an `sse`/`streamable-http`/`http` transport selection, an SSE server/mux/listener, or an `MCP_TRANSPORT` switch). When it does, the source must also show **both** an auth marker (`bearer` / `authorization` / `auth`) **and** a host-guard marker (`127.0.0.1` / `localhost` / `loopback` / `origin`). stdio-only servers pass vacuously.

## Directory submission surface

These rules encode pass/fail criteria from the Anthropic Directory review and the high-leverage capability hints in the upstream SDK guidance. They keep a server that wraps an API the same way Claude's own connector reviewers expect.

### PROTO-018 — Tool names are at most 64 characters [MUST]

**Rationale.** The Anthropic Directory rejects any tool whose name exceeds 64 characters, and several hosts truncate longer names in their UI and permission prompts. A name that survives review on one host but not another is a silent interop failure, so the limit is enforced everywhere.

**Mechanical check.** Every registered tool name (`@mcp.tool` in Python, `WithTools(...)` in Go) is ≤ 64 characters. A server that exposes no tools passes vacuously.

### PROTO-019 — Server sets an `instructions` string [SHOULD]

**Rationale.** The server `instructions` field lands directly in the host's system prompt and is the single highest-leverage place to put cross-tool usage hints ("call `search_*` before `get_*` — IDs aren't guessable") that don't belong in any one tool description. Omitting it leaves the model to infer tool-ordering and preconditions on its own.

**Mechanical check.** Source constructs the server with an instructions string: Python passes `instructions=` to `FastMCP(...)`; Go passes `server.WithInstructions(...)` or sets an `Instructions:` field. Detected as the substring `instructions=` / `Instructions:` / `WithInstructions(` (case-insensitive) anywhere in the server source.

### PROTO-020 — Each tool declares a human-readable `title` [SHOULD]

**Rationale.** The protocol `name` is a `snake_case` identifier (PROTO-001); the `title` annotation is the display label a host shows in tool lists and permission dialogs. The Anthropic Directory expects every tool to carry one. Without it, hosts fall back to the raw identifier and users approve calls against `good_python_delete_widget` instead of "Delete widget".

**Mechanical check.** A repo that defines at least one tool also references a title marker somewhere in its source: a `title=` argument, a `"title"` / `'title'` annotation key, a `Title:` field, or a `WithTitleAnnotation(...)` constructor (case-insensitive). A server that exposes no tools passes vacuously.

### PROTO-021 — Elicitation and sampling calls are guarded by a capability check [MUST]

**Rationale.** Elicitation and sampling depend on client support that not every host advertises. The SDKs raise (`CapabilityNotSupported` in FastMCP) when a tool calls `elicit` / `sample` against a client that never declared the capability, turning an optional nicety into a hard tool failure. A server that uses either feature must check the client's declared capabilities first and fall back gracefully.

**Mechanical check.** Only fires when the source calls an elicitation or sampling primitive (`.elicit(...)` / `.elicitInput(...)`, `ctx.sample(...)` / `.sample(...)`, or `createMessage(...)`). When it does, the source must also reference a capability guard: `CapabilityNotSupported`, `client_capabilities` / `clientCapabilities`, `getClientCapabilities`, `get_client_capabilities`, or `client_params`. A server that uses neither feature passes vacuously.
