"""Rules: MCP protocol (PROTO-001..022)."""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from consistency_check.sources import (
    STRING_LITERAL,
    code_and_literals,
    code_only,
    combined_code_text,
    combined_source_text,
    go_sources,
    mask_literal_braces,
    mask_literal_contents,
    python_sources,
)
from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

# Three registration shapes across the Go SDKs: mcp-go's ``WithTools("name")``
# and ``AddTool(mcp.NewTool("name", ...))``, and the official SDK's
# ``&mcp.Tool{Name: "name"}`` composite literal handed to a register helper. The
# name is read from the first argument only — a wider window captures any string
# in the call (``AddTool(registry.Get("search"), h)``) as a tool name.
# The capture is deliberately ``[^"]*`` and not ``[a-zA-Z0-9_]+``: an anchored
# charset drops the name entirely when it contains anything else, so
# ``NewTool("Bad-Name-Here")`` registered nothing and PROTO-001 — the rule whose
# whole job is catching that name — passed on it.
_GO_TOOL_REGISTER = re.compile(r'WithTools\([^,]*"([^"]*)"|\bNewTool\s*\(\s*"([^"]*)"')
_GO_TOOL_LITERAL = re.compile(r"\bTool\{")
_GO_TOOL_LITERAL_NAME = re.compile(r'\bName:\s*"([^"]*)"')
_GO_TOOL_LITERAL_NAME_FIELD = re.compile(r"\bName:")
_SECRET_NAME = re.compile(r"(?i)(token|key|secret|password|api[_\-]?key)")
# Anchored variant for whole Python identifiers in log calls. ``token``,
# ``secret`` and ``password`` are credentials even standalone, but a bare
# ``key`` is usually a map/loop key — only a *qualified* form (api_key,
# secret_key, signing_key, ...) names a credential. Plural/compound names like
# ``keys`` or ``key_names`` carry field labels, not values, and must not match.
_SECRET_IDENTIFIER = re.compile(
    r"(?i)(?:(?:^|_)(?:token|secret|password|passwd)$|_(?:api_?)?key$|^api_?key$)"
)


def _expected_namespace(repo: Repo) -> str:
    return repo.path.name.removesuffix("-mcp").replace("-", "_") + "_"


def _mask_nested(region: str) -> str:
    """Blank every character inside a nested brace group, keeping offsets stable."""
    out: list[str] = []
    depth = 0
    for ch in region:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        out.append(" " if depth or ch in "{}" else ch)
    return "".join(out)


def _brace_groups(region: str) -> list[str]:
    """Return the contents of each top-level brace group in ``region``."""
    groups: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(region):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                groups.append(region[start + 1 : i])
    return groups


def _literal_tool_names(region: str) -> list[str]:
    """Tool names carried by one ``Tool{...}`` region.

    Only the literal's *own* fields name it, so the region is masked before the
    ``Name`` scan: an inner ``&mcp.Meta{Name: ...}`` would otherwise be read as
    the tool's name. When the region has no ``Name`` of its own it is a slice
    literal (``[]mcp.Tool{{...}, {...}}``), whose elements each name a tool.
    """
    top = _mask_nested(region)
    own = [m.group(1) for m in _GO_TOOL_LITERAL_NAME.finditer(top)]
    if own:
        return own
    # A literal that has a Name field the auditor cannot read — ``Name: toolName``
    # — names exactly one tool, and it is not any nested literal's. Recursing
    # would grade an inner ``&mcp.Meta{Name: "internal_id"}`` as the tool name.
    if _GO_TOOL_LITERAL_NAME_FIELD.search(top):
        return []
    return [name for group in _brace_groups(region) for name in _literal_tool_names(group)]


def _go_tool_names(text: str) -> list[str]:
    """Tool names registered in one Go source file.

    ``Tool{...}`` literals are read with balanced brace matching: Go struct
    fields are unordered, so ``Name`` may sit after a nested composite that a
    ``[^{}]*`` window would stop at.
    """
    text = mask_literal_braces(text)
    names = [next(g for g in m.groups() if g is not None) for m in _GO_TOOL_REGISTER.finditer(text)]
    for m in _GO_TOOL_LITERAL.finditer(text):
        names.extend(_literal_tool_names(_balanced(text, m.end() - 1, "{", "}")))
    return names


def _declared_tool_name(func: _ToolFunc) -> str:
    """Return the name the tool registers under, which need not be the def's name.

    ``@mcp.tool(name="thing-list")`` publishes ``thing-list``; grading the
    function name instead let a non-conforming registered name pass PROTO-001,
    PROTO-002 and PROTO-018 because the def beside it was well formed.
    """
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        for kw in dec.keywords:
            if kw.arg != "name" or not isinstance(kw.value, ast.Constant):
                continue
            if isinstance(kw.value.value, str):
                return kw.value.value
    return func.name


def _tool_names(repo: Repo) -> list[str]:
    if repo.language == "python":
        return [_declared_tool_name(func) for func in _repo_tool_funcs(repo)]
    # Comments are stripped (literals kept) so a registration shape quoted in a
    # doc comment cannot invent a tool name.
    return [
        name
        for p in go_sources(repo)
        for name in _go_tool_names(
            code_and_literals(p.read_text(encoding="utf-8", errors="replace"), "//")
        )
    ]


def _check_snake_case(repo: Repo) -> str | None:
    bad = [n for n in _tool_names(repo) if not re.fullmatch(r"[a-z][a-z0-9_]*", n)]
    return f"non-snake_case tool names: {bad[:5]}" if bad else None


def _check_namespace_prefix(repo: Repo) -> str | None:
    prefix = _expected_namespace(repo)
    bad = [n for n in _tool_names(repo) if not n.startswith(prefix)]
    return f"tools missing {prefix!r} prefix: {bad[:5]}" if bad else None


_ToolFunc = ast.FunctionDef | ast.AsyncFunctionDef


def _decorator_target(dec: ast.expr) -> ast.expr:
    return dec.func if isinstance(dec, ast.Call) else dec


def _is_mcp_tool_decorator(dec: ast.expr) -> bool:
    """``@mcp.tool``, ``@server.tool``, ``@self._mcp.tool`` — any receiver.

    Anchoring on the receiver name ``mcp`` missed every server whose FastMCP
    instance is called something else.
    """
    target = _decorator_target(dec)
    return isinstance(target, ast.Attribute) and target.attr == "tool"


def _applies_tool_decorator(node: ast.AST) -> bool:
    """``mcp.tool(**kwargs)(fn)`` — the decorator built and applied by hand."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Call)
        and isinstance(node.func.func, ast.Attribute)
        and node.func.func.attr == "tool"
    )


def _returns_tool_decorator(node: ast.AST) -> bool:
    """Report whether ``node`` contains a ``return mcp.tool(**kw)(fn)``.

    Requiring the *return* is what separates a decorator factory from a plain
    registration helper (``def register(mcp): mcp.tool()(search)``), whose name
    would otherwise turn every unrelated ``@x.register`` decorator — the
    ``functools.singledispatch`` shape, say — into a phantom tool.
    """
    return any(
        isinstance(inner, ast.Return)
        and inner.value is not None
        and _applies_tool_decorator(inner.value)
        for inner in ast.walk(node)
    )


def _named_funcs(scope: ast.AST) -> list[_ToolFunc]:
    """Collect defs reachable without entering another function's body.

    These are the only names a decorator elsewhere can reference. Descent
    continues through ``if``/``try``/``with`` and class bodies, so a factory
    guarded by a version check is still found, but stops at a function body: a
    factory's inner plumbing is conventionally called ``decorator`` or
    ``wrapper``, and matching a decorator against names that generic collides
    with unrelated code.
    """
    funcs: list[_ToolFunc] = []
    for node in ast.iter_child_nodes(scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node)
        elif not isinstance(node, ast.Lambda):
            funcs.extend(_named_funcs(node))
    return funcs


def _tool_factories(tree: ast.Module) -> set[str]:
    """Names of functions that register a tool on their caller's behalf.

    A repo may wrap registration in its own decorator factory — ``unraid_tool``
    returns a decorator whose body ends in ``mcp.tool(**kw)(wrapper)``. Functions
    decorated with that factory are tools even though no ``.tool`` attribute
    appears at the decoration site.
    """
    return {node.name for node in _named_funcs(tree) if _returns_tool_decorator(node)}


def _is_factory_decorator(dec: ast.expr, factories: frozenset[str]) -> bool:
    target = _decorator_target(dec)
    if isinstance(target, ast.Name):
        return target.id in factories
    # ``@helpers.unraid_tool(mcp)`` — the factory reached through its module.
    return isinstance(target, ast.Attribute) and target.attr in factories


def _is_tool_func(node: _ToolFunc, factories: frozenset[str]) -> bool:
    return any(
        _is_mcp_tool_decorator(dec) or _is_factory_decorator(dec, factories)
        for dec in node.decorator_list
    )


def _python_trees(repo: Repo) -> tuple[list[ast.Module], list[str]]:
    """Parse every Python source, returning the trees and the files that failed.

    The failures are returned rather than dropped because a file the auditor
    cannot parse is a file every Python tool rule is blind to, and blindness
    that reports as a pass is the thing PROTO-022 exists to surface.
    """
    trees: list[ast.Module] = []
    unparseable: list[str] = []
    for p in python_sources(repo):
        try:
            trees.append(ast.parse(p.read_text(encoding="utf-8", errors="replace")))
        except (SyntaxError, ValueError, RecursionError):
            unparseable.append(p.name)
    return trees, unparseable


def _repo_tool_funcs(repo: Repo) -> list[_ToolFunc]:
    """Every tool-registered def in the repo.

    AST-based so generics with commas (``dict[str, Any]``) and long
    signatures/docstrings can't fool a regex, and so tools registered inside
    ``register_*`` helpers are reached. Decorator factories are collected across
    the whole repo because the factory usually lives in a shared helper module.
    """
    trees = _python_trees(repo)[0]
    factories = frozenset[str]().union(*(_tool_factories(t) for t in trees))
    return [
        node
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_tool_func(node, factories)
    ]


def _is_context_param(arg: ast.arg) -> bool:
    if arg.arg in {"self", "ctx", "context"}:
        return True
    ann = arg.annotation
    if isinstance(ann, ast.Name):
        return ann.id == "Context"
    if isinstance(ann, ast.Attribute):
        return ann.attr == "Context"
    return False


def _documentable_args(func: _ToolFunc) -> list[ast.arg]:
    a = func.args
    return [arg for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs) if not _is_context_param(arg)]


def _check_typed_inputs(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad = [
        func.name
        for func in _repo_tool_funcs(repo)
        if any(arg.annotation is None for arg in _documentable_args(func))
    ]
    return f"tools with untyped params: {bad[:5]}" if bad else None


def _check_docstrings(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad: list[str] = []
    for func in _repo_tool_funcs(repo):
        doc = ast.get_docstring(func) or ""
        has_return = "Returns:" in doc or "Yields:" in doc
        has_args = "Args:" in doc
        if not has_return or (_documentable_args(func) and not has_args):
            bad.append(func.name)
    return f"tools missing Args/Returns docstring: {bad[:5]}" if bad else None


# Shared so PROTO-005 (split) and PROTO-006 (gate) recognise the same env-flag
# spellings. PROTO-005 additionally accepts structural separation (register_read
# / register_write); PROTO-006 requires the flag itself.
_WRITE_FLAG = re.compile(r"(?i)(enable_?writes?|allow_?writes?|writes?_enabled)")


def _check_read_write_split(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if _WRITE_FLAG.search(text) or "register_read" in text or "register_write" in text:
        return None
    return "no read/write tool separation detected"


def _check_write_gate(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if _WRITE_FLAG.search(text):
        return None
    return "no env-flag write-gate detected"


def _check_capabilities(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if "FastMCP(" in text or "mcp.NewServer" in text or "Capabilities" in text:
        return None
    return "no capabilities registration detected"


def _check_stdio_default(repo: Repo) -> str | None:
    if repo.language == "go" and not next((p for p in (repo.path / "cmd").rglob("main.go")), None):
        return "no cmd/.../main.go found"
    return None


def _check_mcp_errors(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if "ToolError" in text or "IsError" in text or "CallToolResult" in text:
        return None
    return "no MCP-error-shaped error returns detected"


def _check_error_mapping(repo: Repo) -> str | None:
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"def\s+_classify_\w+|func\s+errToMCP", text):
            return None
    return "no error-mapping helper detected"


def _secret_in_python_args(repo: Repo) -> str | None:
    for p in python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"add_argument\(\s*['\"]([^'\"]+)['\"]", text):
            if _SECRET_NAME.search(m.group(1)):
                return f"secret-shaped CLI arg: {m.group(1)}"
    return None


def _secret_in_go_flags(repo: Repo) -> str | None:
    for p in go_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'flag\.\w+\(\s*"([^"]+)"', text):
            if _SECRET_NAME.search(m.group(1)):
                return f"secret-shaped CLI flag: {m.group(1)}"
    return None


def _check_no_secret_cli_args(repo: Repo) -> str | None:
    if repo.language == "python":
        return _secret_in_python_args(repo)
    return _secret_in_go_flags(repo)


def _check_no_secret_logging(repo: Repo) -> str | None:
    sources = python_sources(repo) if repo.language == "python" else go_sources(repo)
    for p in sources:
        # Strip string-literal contents up front so human-readable format text
        # never reaches the identifier scan, and a ``)`` inside a literal (e.g.
        # "...not set (see README)") cannot truncate the log-call match.
        text = STRING_LITERAL.sub("", p.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"(?:logger|log)\.\w+\(", text):
            # Balanced extraction (not ``[^)]*``) so a credential logged after a
            # nested call — ``logger.info("%s", redact(x), api_key)`` — is still
            # seen; ``[^)]*`` would stop at the first inner ``)``.
            args = _balanced(text, m.end() - 1, "(", ")")
            # The negative lookahead skips identifiers in call position, so a
            # redaction helper (``_scrub_secret(...)``) is not mistaken for a
            # logged credential; only value identifiers are inspected.
            for var in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()", args):
                if _SECRET_IDENTIFIER.search(var):
                    return f"possible secret-shaped variable in log call: {var} ({p.name})"
    return None


def _balanced(text: str, open_idx: int, open_ch: str, close_ch: str) -> str:
    """Return the text enclosed by the delimiter opening at ``open_idx``."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return text[open_idx + 1 :]


_PY_PRINT = re.compile(r"(?<![.\w])print\s*\(")
# A bare `os.Stdout` reference is usually dependency injection — the CLI hands
# os.Stdout to a run() that also serves stdio — not a write that corrupts the
# protocol stream. Flag only actual writes: the fmt.Print* family, an explicit
# fmt.Fprint*(os.Stdout, …), os.Stdout.Write[String], or os.Stdout as the
# destination writer of a copy helper / writer constructor. Only the first
# argument position counts: that is the destination for every helper listed, so
# `io.Copy(w, os.Stdout)` (stdout as *source*) stays clean. io.MultiWriter is the
# exception — it fans out to every argument — so its whole argument list is
# scanned via balanced extraction.
_GO_STDOUT_WRITER_SINKS = (
    r"bufio\.NewWriter(?:Size)?",
    r"io\.Copy(?:N)?",
    r"io\.WriteString",
    r"json\.NewEncoder",
    r"log\.New",
    r"log\.SetOutput",
)
_GO_STDOUT = re.compile(
    r"\bfmt\.(?:Print|Printf|Println)\s*\("
    r"|\bfmt\.Fprint(?:f|ln)?\s*\(\s*os\.Stdout\b"
    r"|\bos\.Stdout\.(?:Write|WriteString)\b"
    rf"|\b(?:{'|'.join(_GO_STDOUT_WRITER_SINKS)})\s*\(\s*os\.Stdout\b",
)
_GO_MULTIWRITER = re.compile(r"\bio\.MultiWriter\s*\(")
_GO_STDOUT_REF = re.compile(r"\bos\.Stdout\b")


def _go_writes_stdout(text: str) -> bool:
    if _GO_STDOUT.search(text):
        return True
    return any(
        _GO_STDOUT_REF.search(_balanced(text, m.end() - 1, "(", ")"))
        for m in _GO_MULTIWRITER.finditer(text)
    )


def _stdout_writers(repo: Repo) -> list[str]:
    bad: list[str] = []
    if repo.language == "python":
        for p in python_sources(repo):
            text = code_only(p.read_text(encoding="utf-8", errors="replace"), "#")
            for m in _PY_PRINT.finditer(text):
                # ``print(..., file=sys.stderr)`` is fine; only stdout corrupts.
                if "file=" not in _balanced(text, m.end() - 1, "(", ")"):
                    bad.append(p.name)
                    break
        return bad
    bad.extend(
        p.name
        for p in go_sources(repo)
        if _go_writes_stdout(code_only(p.read_text(encoding="utf-8", errors="replace"), "//"))
    )
    return bad


def _check_no_stdout_writes(repo: Repo) -> str | None:
    bad = _stdout_writers(repo)
    if bad:
        return f"writes to stdout (corrupts JSON-RPC framing): {sorted(set(bad))[:5]}"
    return None


_PY_HTTP_CLIENT = re.compile(r"httpx\.(?:Async)?Client\s*\(")
_GO_HTTP_CLIENT = re.compile(r"http\.Client\s*\{")


def _untimed_http_clients(repo: Repo) -> list[str]:
    bad: list[str] = []
    if repo.language == "python":
        for p in python_sources(repo):
            text = code_only(p.read_text(encoding="utf-8", errors="replace"), "#")
            bad.extend(
                p.name
                for m in _PY_HTTP_CLIENT.finditer(text)
                if "timeout=" not in _balanced(text, m.end() - 1, "(", ")")
            )
        return bad
    for p in go_sources(repo):
        text = code_only(p.read_text(encoding="utf-8", errors="replace"), "//")
        bad.extend(
            p.name
            for m in _GO_HTTP_CLIENT.finditer(text)
            if "Timeout:" not in _balanced(text, m.end() - 1, "{", "}")
        )
    return bad


def _check_http_timeout(repo: Repo) -> str | None:
    bad = _untimed_http_clients(repo)
    if bad:
        return f"HTTP client constructed without explicit timeout: {sorted(set(bad))[:5]}"
    return None


def _has_description_kwarg(func: _ToolFunc) -> bool:
    return any(
        isinstance(dec, ast.Call)
        and _is_mcp_tool_decorator(dec)
        and any(kw.arg == "description" for kw in dec.keywords)
        for dec in func.decorator_list
    )


def _tool_summary_present(func: _ToolFunc) -> bool:
    for line in (ast.get_docstring(func) or "").splitlines():
        stripped = line.strip()
        if stripped:
            return not stripped.startswith(("Args:", "Returns:", "Yields:", "Raises:"))
    return False


def _check_tool_descriptions(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad = [
        func.name
        for func in _repo_tool_funcs(repo)
        if not _has_description_kwarg(func) and not _tool_summary_present(func)
    ]
    return f"tools missing a description summary line: {bad[:5]}" if bad else None


_ANNOTATION_MARKER = re.compile(
    r"readOnlyHint|destructiveHint|idempotentHint|openWorldHint"
    r"|read_only_hint|destructive_hint|idempotent_hint|open_world_hint"
    r"|ToolAnnotations?"
)


def _check_tool_annotations(repo: Repo) -> str | None:
    if not _tool_names(repo):
        return None
    if _ANNOTATION_MARKER.search(combined_source_text(repo)):
        return None
    return "tools defined but none declare MCP annotations (readOnlyHint/destructiveHint/...)"


_HTTP_TRANSPORT = re.compile(
    r"(?i)transport\s*[=:]\s*['\"](?:sse|streamable-?http|http)"
    r"|streamable[_-]?http|sse[_-]?(?:server|mux|listener)|serveSSE|MCP_TRANSPORT"
)
_TRANSPORT_AUTH = re.compile(r"(?i)\bbearer\b|\bauthorization\b|\bauth\b")
_TRANSPORT_HOST_GUARD = re.compile(r"(?i)127\.0\.0\.1|localhost|loopback|\borigin\b")


def _check_http_transport_security(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if not _HTTP_TRANSPORT.search(text):
        return None
    missing = [
        label
        for label, pattern in (
            ("auth (bearer/token) enforcement", _TRANSPORT_AUTH),
            ("loopback-bind/Origin rebinding guard", _TRANSPORT_HOST_GUARD),
        )
        if not pattern.search(text)
    ]
    if missing:
        return f"HTTP/SSE transport enabled without {', '.join(missing)}"
    return None


def _check_tool_name_length(repo: Repo) -> str | None:
    bad = [n for n in _tool_names(repo) if len(n) > 64]
    return f"tool names exceed 64 chars: {bad[:5]}" if bad else None


# FastMCP ``instructions=`` kwarg, mcp-go ``server.WithInstructions(...)`` option,
# and the official Go SDK's ``Instructions:`` struct field all set the same
# host-system-prompt string.
_SERVER_INSTRUCTIONS = re.compile(r"(?i)instructions\s*[=:]|with_?instructions\s*\(")


def _check_server_instructions(repo: Repo) -> str | None:
    if _SERVER_INSTRUCTIONS.search(combined_source_text(repo)):
        return None
    return "server sets no instructions string"


# The display ``title`` is distinct from the snake_case protocol ``name``; hosts
# show it in tool lists and permission prompts.
_TITLE_MARKER = re.compile(r"(?i)\btitle\s*[=:]|[\"']title[\"']|with_?title_?annotation\s*\(")


def _check_tool_titles(repo: Repo) -> str | None:
    if not _tool_names(repo):
        return None
    if _TITLE_MARKER.search(combined_source_text(repo)):
        return None
    return "tools defined but none declare a human-readable title"


# Trigger: a call to an elicitation/sampling primitive. ``.sample(`` is anchored
# to ``ctx.`` so unrelated data-sampling calls don't fire the rule.
_ELICIT_SAMPLE_CALL = re.compile(r"(?i)\.elicit\w*\s*\(|\bctx\.sample\s*\(|\bcreate_?message\s*\(")
# Guard: ``client_?capabilities`` matches both ``client_capabilities`` and
# ``clientCapabilities`` once case-folded (the camelCase ``C`` lowercases to a
# bare ``c``, so the optional underscore covers both spellings).
_CAPABILITY_GUARD = re.compile(
    r"(?i)CapabilityNotSupported|client_?capabilities"
    r"|get_?client_?capabilities|client_params"
)


# Anchored on the MCP server constructors: a bare ``NewServer(`` also matches
# ``httptest.NewServer(`` and ``grpc.NewServer(``, which are not tool surfaces.
# Bare ``Server(...)`` catches the low-level Python SDK (``app = Server("x")``,
# ``Server(name=...)``, ``Server(SETTINGS.name)``), whose ``@app.list_tools()``
# registrations this module cannot name yet — exactly the state this rule exists
# to report. The receiver lookbehind is what keeps an accessor or an unrelated
# library out: ``cfg.Server()`` and ``uvicorn.Server(cfg)`` are both qualified,
# and at least one argument is required so a no-arg accessor cannot match.
_SERVER_MARKER = re.compile(
    r"FastMCP\s*\(|mcp\.NewServer\s*\(|server\.NewMCPServer\s*\("
    r"|(?<![.\w])Server\s*\(\s*[^)\s]"
)


def _check_tools_detected(repo: Repo) -> str | None:
    if repo.language == "python":
        if not python_sources(repo):
            return "no Python source under src/, so no tool rule read anything"
        if unparseable := _python_trees(repo)[1]:
            return f"source the tool rules could not parse, so never graded: {unparseable[:5]}"
    if _tool_names(repo):
        return None
    # Literal *contents* are masked: an error message that quotes a constructor
    # — ``raise RuntimeError("FastMCP(...) not initialised")`` — made a toolless
    # client library fail a MUST with evidence reading "server constructed".
    if not _SERVER_MARKER.search(mask_literal_contents(combined_code_text(repo))):
        return None
    return (
        "server constructed but no tool registration detected — every tool-surface "
        "rule (PROTO-001..004, 015, 016, 018, 020) passes vacuously here"
    )


def _check_capability_guard(repo: Repo) -> str | None:
    text = combined_source_text(repo)
    if not _ELICIT_SAMPLE_CALL.search(text):
        return None
    if _CAPABILITY_GUARD.search(text):
        return None
    return "elicitation/sampling call without a client-capability check"


RULES: tuple[Rule, ...] = (
    Rule(
        id="PROTO-001",
        tier=Tier.MUST,
        statement="Tool names use snake_case",
        check=_check_snake_case,
        min_stage=Stage.S1,
    ),
    Rule(
        id="PROTO-002",
        tier=Tier.MUST,
        statement="Tool names prefixed with namespace",
        check=_check_namespace_prefix,
        min_stage=Stage.S1,
    ),
    Rule(
        id="PROTO-003",
        tier=Tier.MUST,
        statement="Each tool has a typed input schema",
        check=_check_typed_inputs,
        min_stage=Stage.S1,
    ),
    Rule(
        id="PROTO-004",
        tier=Tier.MUST,
        statement="Each tool has Args/Returns docstring",
        check=_check_docstrings,
        min_stage=Stage.S1,
    ),
    Rule(
        id="PROTO-005",
        tier=Tier.SHOULD,
        statement="Read tools and write tools separated",
        check=_check_read_write_split,
        min_stage=Stage.S2,
    ),
    Rule(
        id="PROTO-006",
        tier=Tier.MUST,
        statement="Write tools require explicit env-flag opt-in",
        check=_check_write_gate,
        min_stage=Stage.S2,
    ),
    Rule(
        id="PROTO-007",
        tier=Tier.MUST,
        statement="Server registers capabilities explicitly",
        check=_check_capabilities,
    ),
    Rule(
        id="PROTO-008",
        tier=Tier.MUST,
        statement="Default transport is stdio",
        check=_check_stdio_default,
    ),
    Rule(
        id="PROTO-009",
        tier=Tier.MUST,
        statement="Errors as MCP error objects",
        check=_check_mcp_errors,
    ),
    Rule(
        id="PROTO-010",
        tier=Tier.SHOULD,
        statement="Error mapping helper present",
        check=_check_error_mapping,
    ),
    Rule(
        id="PROTO-011",
        tier=Tier.MUST,
        statement="No secret-shaped CLI args",
        check=_check_no_secret_cli_args,
    ),
    Rule(
        id="PROTO-012",
        tier=Tier.MUST,
        statement="No secret-shaped variables in log calls",
        check=_check_no_secret_logging,
    ),
    Rule(
        id="PROTO-013",
        tier=Tier.MUST,
        statement="stdout reserved for JSON-RPC (no print/stdout writes)",
        check=_check_no_stdout_writes,
    ),
    Rule(
        id="PROTO-014",
        tier=Tier.MUST,
        statement="Outbound HTTP clients set an explicit timeout",
        check=_check_http_timeout,
    ),
    Rule(
        id="PROTO-015",
        tier=Tier.MUST,
        statement="Each tool has a description summary",
        check=_check_tool_descriptions,
    ),
    Rule(
        id="PROTO-016",
        tier=Tier.SHOULD,
        statement="Tools declare MCP annotations",
        check=_check_tool_annotations,
    ),
    Rule(
        id="PROTO-017",
        tier=Tier.MUST,
        statement="Network transport requires auth and loopback guard",
        check=_check_http_transport_security,
    ),
    Rule(
        id="PROTO-018",
        tier=Tier.MUST,
        statement="Tool names are at most 64 characters",
        check=_check_tool_name_length,
        min_stage=Stage.S1,
    ),
    Rule(
        id="PROTO-019",
        tier=Tier.SHOULD,
        statement="Server sets an instructions string",
        check=_check_server_instructions,
    ),
    Rule(
        id="PROTO-020",
        tier=Tier.SHOULD,
        statement="Each tool declares a human-readable title",
        check=_check_tool_titles,
    ),
    Rule(
        id="PROTO-021",
        tier=Tier.MUST,
        statement="Elicitation/sampling guarded by a capability check",
        check=_check_capability_guard,
    ),
    Rule(
        id="PROTO-022",
        tier=Tier.MUST,
        statement="Server registers at least one detectable tool",
        check=_check_tools_detected,
        min_stage=Stage.S1,
    ),
)
