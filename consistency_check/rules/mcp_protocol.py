"""Rules: MCP protocol (PROTO-001..017)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

# The optional ``(...)`` block (one level of nesting) lets the decorator args
# span multiple lines; without it a split ``@mcp.tool(\n  name=...\n)`` decorator
# matched nothing and the tool was invisible to every PROTO-* tool check. group(0)
# therefore spans the whole decorator, so PROTO-015's ``description=`` test sees
# args on their own line too.
_TOOL_DECORATOR = re.compile(
    r"@mcp\.tool(?:\s*\((?:[^()]|\([^()]*\))*\))?"
    r"[^\n]*\n\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\("
)
_GO_TOOL_REGISTER = re.compile(r'WithTools\([^,]*"([a-zA-Z0-9_]+)"')
_SECRET_NAME = re.compile(r"(?i)(token|key|secret|password|api[_\-]?key)")
# Anchored variant for whole Python identifiers in log calls. ``token``,
# ``secret`` and ``password`` are credentials even standalone, but a bare
# ``key`` is usually a map/loop key — only a *qualified* form (api_key,
# secret_key, signing_key, ...) names a credential. Plural/compound names like
# ``keys`` or ``key_names`` carry field labels, not values, and must not match.
_SECRET_IDENTIFIER = re.compile(
    r"(?i)(?:(?:^|_)(?:token|secret|password|passwd)$|_(?:api_?)?key$|^api_?key$)"
)


def _python_sources(repo: Repo) -> list[Path]:
    src = repo.path / "src"
    return list(src.rglob("*.py")) if src.is_dir() else []


def _go_sources(repo: Repo) -> list[Path]:
    # Skip dot-prefix dirs (.git, .worktrees, .venv, etc.) so stale copies
    # under git worktrees or vendor caches don't poison the heuristics.
    return [
        p
        for p in repo.path.rglob("*.go")
        if not any(part.startswith(".") for part in p.parts) and not p.name.endswith("_test.go")
    ]


def _expected_namespace(repo: Repo) -> str:
    return repo.path.name.removesuffix("-mcp").replace("-", "_") + "_"


def _tool_names(repo: Repo) -> list[str]:
    if repo.language == "python":
        return [
            m.group(1)
            for p in _python_sources(repo)
            for m in _TOOL_DECORATOR.finditer(p.read_text(encoding="utf-8", errors="replace"))
        ]
    return [
        m.group(1)
        for p in _go_sources(repo)
        for m in _GO_TOOL_REGISTER.finditer(p.read_text(encoding="utf-8", errors="replace"))
    ]


def _check_snake_case(repo: Repo) -> str | None:
    bad = [n for n in _tool_names(repo) if not re.fullmatch(r"[a-z][a-z0-9_]*", n)]
    return f"non-snake_case tool names: {bad[:5]}" if bad else None


def _check_namespace_prefix(repo: Repo) -> str | None:
    prefix = _expected_namespace(repo)
    bad = [n for n in _tool_names(repo) if not n.startswith(prefix)]
    return f"tools missing {prefix!r} prefix: {bad[:5]}" if bad else None


def _untyped_params_in_sig(sig: str) -> bool:
    params = [
        s.strip()
        for s in sig.split(",")
        if s.strip() and "self" not in s and "ctx" not in s.lower()
    ]
    return any(":" not in param for param in params)


def _check_typed_inputs(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad: list[str] = []
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOOL_DECORATOR.finditer(text):
            sig_start = m.end()
            paren_close = text.find(")", sig_start)
            sig = text[sig_start:paren_close]
            if _untyped_params_in_sig(sig):
                bad.append(m.group(1))
    return f"tools with untyped params: {bad[:5]}" if bad else None


def _has_docstring_sections(after: str) -> bool:
    return "Args:" in after and ("Returns:" in after or "Yields:" in after)


def _check_docstrings(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad: list[str] = []
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOOL_DECORATOR.finditer(text):
            after = text[m.end() : m.end() + 600]
            if not _has_docstring_sections(after):
                bad.append(m.group(1))
    return f"tools missing Args/Returns docstring: {bad[:5]}" if bad else None


def _combined_source_text(repo: Repo) -> str:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)


# Shared so PROTO-005 (split) and PROTO-006 (gate) recognise the same env-flag
# spellings. PROTO-005 additionally accepts structural separation (register_read
# / register_write); PROTO-006 requires the flag itself.
_WRITE_FLAG = re.compile(r"(?i)(enable_?writes?|allow_?writes?|writes?_enabled)")


def _check_read_write_split(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if _WRITE_FLAG.search(text) or "register_read" in text or "register_write" in text:
        return None
    return "no read/write tool separation detected"


def _check_write_gate(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if _WRITE_FLAG.search(text):
        return None
    return "no env-flag write-gate detected"


def _check_capabilities(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if "FastMCP(" in text or "mcp.NewServer" in text or "Capabilities" in text:
        return None
    return "no capabilities registration detected"


def _check_stdio_default(repo: Repo) -> str | None:
    if repo.language == "go" and not next((p for p in (repo.path / "cmd").rglob("main.go")), None):
        return "no cmd/.../main.go found"
    return None


def _check_mcp_errors(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if "ToolError" in text or "IsError" in text or "CallToolResult" in text:
        return None
    return "no MCP-error-shaped error returns detected"


def _check_error_mapping(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"def\s+_classify_\w+|func\s+errToMCP", text):
            return None
    return "no error-mapping helper detected"


def _secret_in_python_args(repo: Repo) -> str | None:
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"add_argument\(\s*['\"]([^'\"]+)['\"]", text):
            if _SECRET_NAME.search(m.group(1)):
                return f"secret-shaped CLI arg: {m.group(1)}"
    return None


def _secret_in_go_flags(repo: Repo) -> str | None:
    for p in _go_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'flag\.\w+\(\s*"([^"]+)"', text):
            if _SECRET_NAME.search(m.group(1)):
                return f"secret-shaped CLI flag: {m.group(1)}"
    return None


def _check_no_secret_cli_args(repo: Repo) -> str | None:
    if repo.language == "python":
        return _secret_in_python_args(repo)
    return _secret_in_go_flags(repo)


_STRING_LITERAL = re.compile(
    r"""
    '''.*?'''               # triple single
    | \"\"\".*?\"\"\"       # triple double
    | "(?:\\.|[^"\\])*"     # double-quoted
    | '(?:\\.|[^'\\])*'     # single-quoted
    """,
    re.VERBOSE | re.DOTALL,
)


def _check_no_secret_logging(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    for p in sources:
        # Strip string-literal contents up front so human-readable format text
        # never reaches the identifier scan, and a ``)`` inside a literal (e.g.
        # "...not set (see README)") cannot truncate the log-call match.
        text = _STRING_LITERAL.sub("", p.read_text(encoding="utf-8", errors="replace"))
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


def _code_only(text: str, line_comment: str) -> str:
    # Drop string literals (docstrings included) then line comments so a
    # ``print(`` mentioned in prose cannot register as a real call.
    text = _STRING_LITERAL.sub("", text)
    return re.sub(rf"{re.escape(line_comment)}.*", "", text)


_PY_PRINT = re.compile(r"(?<![.\w])print\s*\(")
_GO_STDOUT = re.compile(r"\bfmt\.(?:Print|Printf|Println)\s*\(|\bos\.Stdout\b")


def _stdout_writers(repo: Repo) -> list[str]:
    bad: list[str] = []
    if repo.language == "python":
        for p in _python_sources(repo):
            text = _code_only(p.read_text(encoding="utf-8", errors="replace"), "#")
            for m in _PY_PRINT.finditer(text):
                # ``print(..., file=sys.stderr)`` is fine; only stdout corrupts.
                if "file=" not in _balanced(text, m.end() - 1, "(", ")"):
                    bad.append(p.name)
                    break
        return bad
    bad.extend(
        p.name
        for p in _go_sources(repo)
        if _GO_STDOUT.search(_code_only(p.read_text(encoding="utf-8", errors="replace"), "//"))
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
        for p in _python_sources(repo):
            text = _code_only(p.read_text(encoding="utf-8", errors="replace"), "#")
            bad.extend(
                p.name
                for m in _PY_HTTP_CLIENT.finditer(text)
                if "timeout=" not in _balanced(text, m.end() - 1, "(", ")")
            )
        return bad
    for p in _go_sources(repo):
        text = _code_only(p.read_text(encoding="utf-8", errors="replace"), "//")
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


def _tool_summary_present(after: str) -> bool:
    m = re.search(r"(\"\"\"|''')", after)
    if not m:
        return False
    rest = after[m.end() :]
    end = rest.find(m.group(1))
    body = rest if end == -1 else rest[:end]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return not stripped.startswith(("Args:", "Returns:", "Yields:", "Raises:"))
    return False


def _check_tool_descriptions(repo: Repo) -> str | None:
    if repo.language != "python":
        return None
    bad: list[str] = []
    for p in _python_sources(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOOL_DECORATOR.finditer(text):
            if "description=" in m.group(0):
                continue
            if not _tool_summary_present(text[m.end() : m.end() + 600]):
                bad.append(m.group(1))
    return f"tools missing a description summary line: {bad[:5]}" if bad else None


_ANNOTATION_MARKER = re.compile(
    r"readOnlyHint|destructiveHint|idempotentHint|openWorldHint"
    r"|read_only_hint|destructive_hint|idempotent_hint|open_world_hint"
    r"|ToolAnnotations?"
)


def _check_tool_annotations(repo: Repo) -> str | None:
    if not _tool_names(repo):
        return None
    if _ANNOTATION_MARKER.search(_combined_source_text(repo)):
        return None
    return "tools defined but none declare MCP annotations (readOnlyHint/destructiveHint/...)"


_HTTP_TRANSPORT = re.compile(
    r"(?i)transport\s*[=:]\s*['\"](?:sse|streamable-?http|http)"
    r"|streamable[_-]?http|sse[_-]?(?:server|mux|listener)|serveSSE|MCP_TRANSPORT"
)
_TRANSPORT_AUTH = re.compile(r"(?i)\bbearer\b|\bauthorization\b|\bauth\b")
_TRANSPORT_HOST_GUARD = re.compile(r"(?i)127\.0\.0\.1|localhost|loopback|\borigin\b")


def _check_http_transport_security(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
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
        statement="HTTP/SSE transport requires auth and loopback guard",
        check=_check_http_transport_security,
    ),
)
