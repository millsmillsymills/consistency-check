"""Rules: MCP protocol (PROTO-001..012)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

_TOOL_DECORATOR = re.compile(
    r"@mcp\.tool[^\n]*\n\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\("
)
_GO_TOOL_REGISTER = re.compile(r'WithTools\([^,]*"([a-zA-Z0-9_]+)"')
_SECRET_NAME = re.compile(r"(?i)(token|key|secret|password|api[_\-]?key)")


def _python_sources(repo: Repo) -> list[Path]:
    src = repo.path / "src"
    return list(src.rglob("*.py")) if src.is_dir() else []


def _go_sources(repo: Repo) -> list[Path]:
    return [
        p
        for p in repo.path.rglob("*.go")
        if ".git" not in p.parts and not p.name.endswith("_test.go")
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


def _check_read_write_split(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if (
        "ENABLE_WRITE" in text
        or "AllowWrites" in text
        or "register_read" in text
        or "register_write" in text
    ):
        return None
    return "no read/write tool separation detected"


def _check_write_gate(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if re.search(r"(?i)(ENABLE_WRITE|ALLOW_WRITE|writes?_enabled)", text):
        return None
    return "no env-flag write-gate detected"


def _check_capabilities(repo: Repo) -> str | None:
    text = _combined_source_text(repo)
    if "FastMCP(" in text or "mcp.NewServer" in text or "Capabilities" in text:
        return None
    return "no capabilities registration detected"


def _check_stdio_default(repo: Repo) -> str | None:
    if repo.language == "go" and not next(
        (p for p in (repo.path / "cmd").rglob("main.go")), None
    ):
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


def _secret_var_in_log_call(call: str) -> str | None:
    for var in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", call):
        if _SECRET_NAME.search(var):
            return var
    return None


def _check_no_secret_logging(repo: Repo) -> str | None:
    sources = _python_sources(repo) if repo.language == "python" else _go_sources(repo)
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:logger|log)\.\w+\([^)]*\)", text):
            secret_var = _secret_var_in_log_call(m.group(0))
            if secret_var:
                return f"possible secret-shaped variable in log call: {secret_var} ({p.name})"
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="PROTO-001",
        tier=Tier.MUST,
        statement="Tool names use snake_case",
        check=_check_snake_case,
    ),
    Rule(
        id="PROTO-002",
        tier=Tier.MUST,
        statement="Tool names prefixed with namespace",
        check=_check_namespace_prefix,
    ),
    Rule(
        id="PROTO-003",
        tier=Tier.MUST,
        statement="Each tool has a typed input schema",
        check=_check_typed_inputs,
    ),
    Rule(
        id="PROTO-004",
        tier=Tier.MUST,
        statement="Each tool has Args/Returns docstring",
        check=_check_docstrings,
    ),
    Rule(
        id="PROTO-005",
        tier=Tier.SHOULD,
        statement="Read tools and write tools separated",
        check=_check_read_write_split,
    ),
    Rule(
        id="PROTO-006",
        tier=Tier.MUST,
        statement="Write tools require explicit env-flag opt-in",
        check=_check_write_gate,
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
)
