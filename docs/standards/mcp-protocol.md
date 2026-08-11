# MCP Protocol Standards (`PROTO-*`)

Applies to every MCP server. Anchored on the upstream MCP specification (modelcontextprotocol.io, revision `2026-07-28`) and idiomatic SDK patterns (FastMCP for Python, mcp-go for Go).

## Spec revision 2026-07-28

The `2026-07-28` revision makes the protocol stateless — no `initialize` handshake or `Mcp-Session-Id`; protocol version and capabilities travel per-request in `_meta` and are advertised via `server/discover` — and formally deprecates Roots, Sampling, protocol-level Logging, the HTTP+SSE transport, and OAuth Dynamic Client Registration. New servers must not adopt deprecated features; the rules below call out the legacy markers where the auditor can detect them.

Four of this revision's new requirements are audited by PROTO-023..026 below. They are `SHOULD` at `min_stage = S4`: no SDK in the suite emits these fields yet, so a repo that declares a stage below S4 is not graded, and a repo waiting on its SDK reports work toward S4 rather than a MUST failure. An unstaged repo is still graded, since the auditor runs every rule when no stage is declared (see stages.md). Promote them to `MUST` once the SDKs ship the fields.

Guidance from this revision still not mechanically audited: server-initiated requests are replaced by Multi Round-Trip Requests (`resultType: "input_required"`); long-running work uses the `io.modelcontextprotocol/tasks` extension.

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

**Note (2026-07-28).** The stateless revision advertises capabilities per-request in `_meta` and via `server/discover`; SDK-level registration is the source those are derived from, so the check is unchanged.

### PROTO-008 — Default transport is stdio; Streamable HTTP behind explicit flag [MUST]

**Rationale.** stdio is the lowest-friction transport for desktop clients and the project default. The legacy HTTP+SSE transport is Deprecated as of spec `2026-07-28` — migrate to Streamable HTTP; never add SSE to new code.

**Mechanical check.** `__main__.py` (Python) or `main.go` (Go) starts in stdio mode unless a `--transport http|streamable-http` flag (or matching env var) is set.

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

**Mechanical check.** Source contains no stdout write. Python: no `print(...)` call without `file=` routing it elsewhere. Go: no `fmt.Print`/`Printf`/`Println`, no `fmt.Fprint*(os.Stdout, …)`, no `os.Stdout.Write`/`WriteString`, and no `os.Stdout` as the destination writer of `io.Copy`/`CopyN`, `io.WriteString`, `bufio.NewWriter`/`NewWriterSize`, `json.NewEncoder`, or `log.New`/`SetOutput`. Only the destination (first) argument position counts, so `io.Copy(w, os.Stdout)` — stdout as a source — and `os.Stdout` handed to a plain function parameter are dependency injection, not writes. `io.MultiWriter` is checked in every argument position, since it fans out to all of them. Diagnostics go to stderr (see MCP-021).

### PROTO-014 — Outbound HTTP clients set an explicit timeout [MUST]

**Rationale.** A client with no timeout can hang indefinitely and stall the host waiting on the tool. Go's `http.Client` has no default timeout; an explicit one is mandatory and is required everywhere for clarity.

**Mechanical check.** Every HTTP client construction sets a timeout. Python: `httpx.Client(...)` / `httpx.AsyncClient(...)` includes a `timeout=` argument. Go: `http.Client{...}` includes a `Timeout:` field.

### PROTO-015 — Each tool has a description summary [MUST]

**Rationale.** The host model selects tools from their description. A tool with typed Args but no summary line (see PROTO-004) ships blind to the model.

**Mechanical check.** Each `@mcp.tool` function either passes `description=` to the decorator or opens with a docstring whose first non-empty line is a summary (not an `Args:`/`Returns:` section header).

### PROTO-016 — Tools declare MCP annotations [SHOULD]

**Rationale.** MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) let a host gate or auto-approve calls — read-only tools can run unattended, destructive ones can demand confirmation. Without them the client must treat every tool as opaque and equally dangerous.

**Mechanical check.** A repo that defines at least one tool also references a tool-annotation marker somewhere in its source: one of `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` (or their snake_case forms) or a `ToolAnnotations` constructor. A server that exposes no tools passes vacuously.

### PROTO-017 — Network transport requires auth and a loopback guard [MUST]

**Rationale.** PROTO-008 keeps stdio the default and puts Streamable HTTP behind a flag, but once a network transport is enabled the server is reachable by other processes and, via DNS rebinding, by web pages. The MCP spec requires local HTTP servers to authenticate requests and to validate the `Origin`/`Host` header (or bind to loopback) so a browser cannot drive the server.

**Mechanical check.** Only fires when the source enables a network transport (an `sse`/`streamable-http`/`http` transport selection, an SSE server/mux/listener, or an `MCP_TRANSPORT` switch — the `sse` markers stay in the check to catch the deprecated legacy transport). When it does, the source must also show **both** an auth marker (`bearer` / `authorization` / `auth`) **and** a host-guard marker (`127.0.0.1` / `localhost` / `loopback` / `origin`). stdio-only servers pass vacuously.

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

**Note (2026-07-28).** Sampling is Deprecated — new servers must not adopt it; integrate with the LLM provider API directly. Elicitation is restructured as Multi Round-Trip Requests (`resultType: "input_required"`). The guard requirement stands wherever the legacy primitives still appear.

### PROTO-022 — Server registers at least one detectable tool [MUST]

**Rationale.** Every tool-surface rule (PROTO-001..004, 015, 016, 018, 020) derives its subject from the registrations the auditor can find. When it finds none, all of them pass, and a vacuous pass is indistinguishable from a real one in the report — a server reads as fully compliant on its entire tool surface precisely because none of it was audited. This rule makes that state visible.

**Mechanical check.** Two conditions, either of which fails the rule.

First, every Python source under `src/` must parse. A file the auditor cannot parse is a file every Python tool rule skips, and the evidence names it. Second, a repo whose source constructs a server must register at least one tool the auditor can name. A construction is `FastMCP(...)`, `mcp.NewServer(...)`, `server.NewMCPServer(...)`, or an unqualified `Server(...)` with at least one argument — the low-level Python SDK. A qualified call is not a construction, so `httptest.NewServer`, `grpc.NewServer`, `uvicorn.Server(cfg)`, and an accessor like `cfg.Server()` are all excluded.

Python registrations are found by AST: any decorator whose attribute is `tool` (`@mcp.tool`, `@server.tool`), and any decorator naming a factory that returns `x.tool(...)` applied to a function. Factory names are collected from every scope except another function's body, so a factory behind a version check counts while a factory's inner `decorator`/`wrapper` plumbing does not. Go registrations are found by pattern: `WithTools("name")`, `AddTool(...)` / `NewTool("name", ...)`, and a `Tool{Name: "name"}` composite literal, whose name is read from the literal's own depth-0 fields and, for a `[]Tool{...}` slice, from each element. A repo that constructs no server — a library, a client — passes.

Failing this rule means the tool rules above carry no signal for that repo; fix the registration shape (or the matcher) before reading them as passes.

**Known limit (PROTO-022).** The rule fires on *total* blindness, not partial. One detected tool suppresses it, so a repo whose registrations use two shapes — one matched, one not — still reports a clean tool surface for the unmatched half. Catching that needs a count of registration *sites* to compare against the count of named tools, which no reliable pattern yields across the SDKs in use. Treat a repo's tool count as a lower bound.

## Spec revision 2026-07-28 surface

The four rules below grade the stateless revision's new requirements. Each is `SHOULD` at `min_stage = S4` for the reason given at the top of this file. All four detect a marker in source, not the wire shape, since the auditor never runs the server.

**Known limit (PROTO-023..025).** These three markers *are* string literals on the wire — a method name, two JSON keys — so their checks read literals as well as code. Any identifier or string of that name anywhere under `src/` satisfies them: a domain `class ResultType`, an unrelated cache layer's `ttl_ms`, or a `raise NotImplementedError("server/discover is not supported")` all read as compliance. Treat a pass as "the name appears", not "the field ships". PROTO-026 is the inverse case and reads code with literals stripped, so a migration note that names the retired code does not fail a repo that has migrated away from it.

### PROTO-023 — Server exposes a `server/discover` handler [SHOULD]

**Rationale.** The `2026-07-28` revision removes the `initialize` handshake. A client learns a server's protocol version and capabilities from `server/discover`; a server that never answers it is undiscoverable to a stateless client.

**Mechanical check.** Source references `server/discover` (the method string) or a `server_discover` / `serverDiscover` identifier, case-insensitively. Comments and Python docstrings are stripped first; string literals are kept, since the method name is one.

### PROTO-024 — Results carry a `resultType` field [SHOULD]

**Rationale.** `resultType` is how a stateless client tells a finished result from one that needs another round trip (`resultType: "input_required"`, which replaces server-initiated elicitation). Without it a client cannot drive a multi-round-trip tool.

**Mechanical check.** Source references `resultType` or `result_type` (case-insensitive) outside comments and docstrings. String literals count, since the field is a JSON key.

### PROTO-025 — List and read results carry `ttlMs` and `cacheScope` [SHOULD]

**Rationale.** Statelessness moves caching to the client. `ttlMs` and `cacheScope` on list and read results are what let a client reuse a result instead of re-listing on every request; omitting them turns every tool list into a round trip.

**Mechanical check.** Source references both `ttlMs`/`ttl_ms` and `cacheScope`/`cache_scope` (case-insensitive) outside comments and docstrings, string literals included. The evidence names whichever is absent.

### PROTO-026 — Resource-not-found uses `-32602`, not the retired `-32002` [SHOULD]

**Rationale.** This revision moves resource-not-found from the `-32002` server-defined code to the JSON-RPC `-32602` (invalid params). A server still returning `-32002` reports a code a conforming client no longer recognises as not-found.

**Mechanical check.** Fails when `-32002` appears in source with comments, docstrings, *and* string literals stripped, so a note or an error message that names the retired code does not fail the repo that has migrated away from it. The sign must sit against the digits, so formatted subtraction (`n - 32002`) does not match, and a preceding word character or `.` suppresses the match so an identifier ending in those digits does not either. A server that returns neither code passes vacuously: this rule detects the retired code, it does not require the new one, because a repo may legitimately expose no resources.
