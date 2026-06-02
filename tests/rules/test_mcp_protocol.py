"""Tests for PROTO-* rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.mcp_protocol import RULES

if TYPE_CHECKING:
    from pathlib import Path
from consistency_check.types import Repo


def _check(p: Path, lang: str, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name=p.name, path=p, language=lang, github_slug="x/y"),
    )


def test_proto_002_pass_on_namespaced_tools(tmp_path: Path) -> None:
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef good_python_list_things(): pass\n", encoding="utf-8"
    )
    assert _check(repo_root, "python", "PROTO-002") is None


def test_proto_002_fail_on_unprefixed_tool(tmp_path: Path) -> None:
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text("@mcp.tool\ndef list_things(): pass\n", encoding="utf-8")
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_002_detects_multiline_decorator_tool(tmp_path: Path) -> None:
    # A decorator whose args span lines used to match nothing, hiding the tool.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(\n    name="x",\n)\ndef list_things(): pass\n', encoding="utf-8"
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_015_pass_with_multiline_decorator_description(tmp_path: Path) -> None:
    # ``description=`` on its own decorator line must satisfy PROTO-015.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(\n    description="List things",\n)\n'
        'def good_python_list(x: int) -> str:\n    return ""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is None


def test_proto_015_fail_on_undescribed_multiline_tool(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(\n    name="x",\n)\ndef good_python_list(x: int) -> str:\n    return ""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is not None


def test_proto_011_fail_on_token_cli_arg(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "__main__.py").write_text('parser.add_argument("--api-key")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-011") is not None


def test_proto_012_pass_when_secret_word_only_in_string_literal(tmp_path: Path) -> None:
    # Regression for the unraid-mcp #171 false positive: the warning text
    # contains "API key" as human-readable text, not a variable name.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        'logger.warning("an attacker can capture the API key.", config.base_url)\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-012") is None


def test_proto_012_fail_when_secret_var_actually_logged(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('logger.info("logging in with %s", api_key)\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-012") is not None


def test_proto_012_pass_when_logging_key_names_not_values(tmp_path: Path) -> None:
    # Regression for the unifi-mcp false positive: ``keys`` is a list of body
    # field *names* (value-free), not a credential. Plural/compound key names
    # must not trip the secret-variable check.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        'logger.info("PATCH %s keys=[%s]", path, ", ".join(keys))\n', encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-012") is None


def test_proto_012_pass_when_secret_name_in_string_with_inner_paren(tmp_path: Path) -> None:
    # Regression for the shortcut-mcp false positive: a ``)`` inside the format
    # string used to truncate the log-call match before the literal was stripped,
    # leaving the secret-shaped word visible to the identifier scan.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        'logger.error("Shortcut tools disabled: SHORTCUT_API_TOKEN not set (see README)")\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-012") is None


def test_proto_012_pass_when_bare_key_loop_var_logged(tmp_path: Path) -> None:
    # Regression for the flipperzero-mcp false positive: ``key`` here is a device
    # property name iterated in a loop, not a credential. Only qualified forms
    # (api_key, secret_key, ...) name secrets.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "rpc.py").write_text(
        'logger.debug("property.get(%s) failed", key, exc_info=True)\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-012") is None


def test_proto_012_fail_when_qualified_key_logged(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('logger.info("using %s", api_key)\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-012") is not None


def test_proto_012_pass_when_redaction_helper_called_in_log(tmp_path: Path) -> None:
    # Regression for the unifi-mcp false positive: ``_scrub_secret`` is a
    # redaction helper invoked in the log call, not a logged credential.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "base.py").write_text(
        'logger.debug("response: %s", self._scrub_secret(str(payload)))\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-012") is None


def test_proto_012_fail_when_secret_after_nested_call(tmp_path: Path) -> None:
    # The matcher used to stop at the first ``)``, so a credential logged after
    # a nested call (here ``redact(other)``) went unseen.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        'logger.info("auth %s %s", redact(other), api_key)\n', encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-012") is not None


def test_proto_005_pass_with_writes_enabled_gate(tmp_path: Path) -> None:
    # A ``writes_enabled`` mode gate separates read tools from write tools even
    # when both register through a single entry point.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "def register_all_tools(mcp, config):\n    if not config.writes_enabled:\n        return\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-005") is None


def test_proto_005_fail_without_separation(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text("def register_all_tools(mcp):\n    pass\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-005") is not None


def test_proto_013_fail_on_bare_print(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('print("starting up")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-013") is not None


def test_proto_013_pass_when_print_routed_to_stderr(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        'import sys\nprint("diagnostic", file=sys.stderr)\n# print("commented out")\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-013") is None


def test_proto_013_pass_on_console_print_method(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text("console.print('hello')\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-013") is None


def test_proto_013_fail_on_go_fmt_println(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        'package internal\nimport "fmt"\nfunc Boot() { fmt.Println("up") }\n', encoding="utf-8"
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_014_fail_on_httpx_client_without_timeout(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        "import httpx\nc = httpx.AsyncClient(base_url=url)\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-014") is not None


def test_proto_014_pass_when_timeout_set(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        "import httpx\nc = httpx.AsyncClient(base_url=url, timeout=10.0)\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-014") is None


def test_proto_014_fail_when_timeout_only_in_identifier(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        "import httpx\nc = httpx.AsyncClient(headers=build_timeout_headers())\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-014") is not None


def test_proto_014_fail_on_go_client_without_timeout(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "http.go").write_text(
        'package internal\nimport "net/http"\nvar c = &http.Client{Transport: t}\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-014") is not None


def test_proto_015_fail_when_tool_has_no_summary(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef good_python_list(x: int) -> str:\n"
        '    """\n    Args:\n        x: count.\n    Returns:\n        text.\n    """\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is not None


def test_proto_015_pass_with_summary_line(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool\ndef good_python_list(x: int) -> str:\n    """List things."""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is None


def test_proto_015_pass_with_decorator_description(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(description="List things")\n'
        'def good_python_list(x: int) -> str:\n    return ""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is None


def test_proto_016_pass_with_annotated_tool(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(annotations={"readOnlyHint": True})\n'
        "def good_python_list(x: int) -> str:\n    return ''\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-016") is None


def test_proto_016_fail_when_tool_unannotated(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef good_python_list(x: int) -> str:\n    return ''\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-016") is not None


def test_proto_016_pass_when_no_tools_defined(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text("mcp = FastMCP('good-python')\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-016") is None


def test_proto_017_pass_for_stdio_only_server(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text("mcp.run(transport='stdio')\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-017") is None


def test_proto_017_fail_on_sse_without_auth(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text("mcp.run(transport='sse', host='0.0.0.0')\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-017") is not None


def test_proto_017_fail_when_guard_words_only_substrings(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        "mcp.run(transport='sse', host='0.0.0.0')\noriginator = author = 'x'\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-017") is not None


def test_proto_017_pass_on_sse_with_auth_and_loopback(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "sse.go").write_text(
        "package internal\nfunc serveSSE() { /* Authorization: Bearer token, bind 127.0.0.1 */ }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-017") is None
