"""Tests for PROTO-* rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.mcp_protocol import RULES, _tool_names

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


def test_proto_002_detects_tool_on_a_non_mcp_receiver(tmp_path: Path) -> None:
    # shortcut-mcp names its FastMCP instance ``server``; anchoring the decorator
    # on the receiver name ``mcp`` hid every one of its tools.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@server.tool(\n    name="x",\n)\ndef list_things(): pass\n', encoding="utf-8"
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_002_detects_tool_registered_through_a_local_factory(tmp_path: Path) -> None:
    # unraid-mcp wraps registration in its own decorator factory, so no ``.tool``
    # attribute appears at the decoration site.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "_helpers.py").write_text(
        "def unraid_tool(mcp, **tool_kwargs):\n"
        "    def decorator(fn):\n"
        "        async def wrapper(*a, **kw):\n"
        "            return await fn(*a, **kw)\n"
        "        return mcp.tool(**tool_kwargs)(wrapper)\n"
        "    return decorator\n",
        encoding="utf-8",
    )
    (pkg / "tools.py").write_text(
        'from good_python._helpers import unraid_tool\n\n@unraid_tool(mcp, tags={"system"})\n'
        "async def list_things(): pass\n",
        encoding="utf-8",
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_factory_indirection_names_the_tool_not_the_plumbing(tmp_path: Path) -> None:
    # The factory's own ``decorator``/``wrapper`` carry neither the tool's name
    # nor its signature, so only the decorated function counts.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "_helpers.py").write_text(
        "def good_python_tool(mcp, **tool_kwargs):\n"
        "    def decorator(fn):\n"
        "        async def wrapper(*a, **kw):\n"
        "            return await fn(*a, **kw)\n"
        "        return mcp.tool(**tool_kwargs)(wrapper)\n"
        "    return decorator\n",
        encoding="utf-8",
    )
    (pkg / "tools.py").write_text(
        "from good_python._helpers import good_python_tool\n\n@good_python_tool(mcp)\n"
        "async def good_python_list(): pass\n",
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == ["good_python_list"]


def test_module_qualified_factory_decorator_is_detected(tmp_path: Path) -> None:
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "_helpers.py").write_text(
        "def unraid_tool(mcp, **kw):\n"
        "    def decorator(fn):\n"
        "        async def wrapper(*a, **k):\n"
        "            return await fn(*a, **k)\n"
        "        return mcp.tool(**kw)(wrapper)\n"
        "    return decorator\n",
        encoding="utf-8",
    )
    (pkg / "tools.py").write_text(
        "from good_python import _helpers\n\n@_helpers.unraid_tool(mcp)\n"
        "async def list_things(): pass\n",
        encoding="utf-8",
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_tool_nested_in_a_registration_helper_is_still_detected(tmp_path: Path) -> None:
    # A helper that both nests decorated tools and hand-applies one registration
    # must not hide the nested tools: partial blindness reads as compliance
    # because the no-tools guard only fires at zero.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "def register_admin(mcp):\n"
        "    @mcp.tool()\n"
        "    async def delete_everything(q: str) -> str:\n"
        "        return q\n"
        '    mcp.tool(name="good_python_other")(other)\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert "delete_everything" in _tool_names(repo)
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_go_tool_name_ignores_later_arguments_of_the_registration_call(tmp_path: Path) -> None:
    # Only the first argument names the tool; a wider window turns any string in
    # the call into a phantom tool name graded by PROTO-001/002/018.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc Register(s *server.MCPServer) {\n"
        '\ts.AddTool(mcp.NewTool("good_go_search", mcp.WithDescription("BadName")), handle)\n}\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["good_go_search"]


def test_go_tool_literal_finds_name_after_a_nested_composite(tmp_path: Path) -> None:
    # Go struct fields are unordered, so Name can follow a nested literal.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc register(s *mcp.Server) {\n"
        "\taddTool(s, &mcp.Tool{\n"
        "\t\tAnnotations: &mcp.ToolAnnotations{ReadOnlyHint: true},\n"
        '\t\tName:        "BadName",\n\t}, handle)\n}\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_go_tool_name_quoted_in_a_comment_is_not_a_tool(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "doc.go").write_text(
        'package internal\n// Registrations look like mcp.Tool{Name: "BadName"} here.\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == []


def test_proto_001_detects_go_add_tool_registration(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc Register(s *server.MCPServer) {\n"
        '\ts.AddTool(mcp.NewTool("BadName"), handle)\n}\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_proto_001_detects_go_tool_composite_literal(tmp_path: Path) -> None:
    # protonmail-mcp registers through a helper taking a &mcp.Tool{...} literal,
    # which the WithTools-only matcher never saw.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc registerAddresses(server *mcp.Server, d Deps) {\n"
        '\taddTool(server, d, &mcp.Tool{\n\t\tName:        "BadName",\n'
        '\t\tDescription: "Lists addresses.",\n\t}, handle)\n}\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_go_tool_literal_name_comes_from_the_literals_own_fields(tmp_path: Path) -> None:
    # A nested composite carries its own Name. Reading the first one in the
    # brace region grades the wrong string as the tool name.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc register(s *mcp.Server) {\n"
        "\taddTool(s, &mcp.Tool{\n"
        '\t\tMeta:        &mcp.Meta{Name: "INNER_WRONG"},\n'
        '\t\tName:        "good_go_search",\n\t}, handle)\n}\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["good_go_search"]


def test_go_tool_slice_literal_names_every_element(tmp_path: Path) -> None:
    # Taking one match per brace region hides every tool after the first, while
    # PROTO-022 still passes because the list is non-empty.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nvar all = []mcp.Tool{\n"
        '\t{Name: "good_go_search"},\n\t{Name: "good_go_fetch"},\n}\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["good_go_search", "good_go_fetch"]


def test_go_tool_name_in_a_block_comment_is_not_a_tool(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "doc.go").write_text(
        "package internal\n/* Registrations look like\n"
        'mcp.Tool{Name: "BadName"} here. */\nvar x = 1\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == []


def test_go_block_comment_stripping_keeps_string_literals(tmp_path: Path) -> None:
    # A `/*` inside a URL must not open a comment that swallows the file: the
    # registration after it would vanish and every tool rule would pass.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\n"
        'const base = "https://example.com/*/things"\n'
        'func Register(s *server.MCPServer) { s.AddTool(mcp.NewTool("BadName"), handle) }\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["BadName"]


def test_registration_helper_is_not_treated_as_a_decorator_factory(tmp_path: Path) -> None:
    # `register` calls but does not *return* the built decorator, so it is a
    # plain helper. Collecting it made every `@x.register` — the singledispatch
    # shape — register a phantom tool named `_`.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "import functools\n\n"
        "def register(mcp):\n    mcp.tool()(search)\n\n"
        "@functools.singledispatch\ndef process(x): ...\n\n"
        "@process.register\ndef _(x: int): return x\n",
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == []


def test_nested_plumbing_names_do_not_become_factories(tmp_path: Path) -> None:
    # `decorator` is a factory's inner plumbing, generic enough to collide with
    # any unrelated decorator of that name.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "_helpers.py").write_text(
        "def good_python_tool(mcp, **kw):\n"
        "    def decorator(fn):\n"
        "        return mcp.tool(**kw)(fn)\n"
        "    return decorator\n",
        encoding="utf-8",
    )
    (pkg / "other.py").write_text("@decorator\ndef unrelated(): pass\n", encoding="utf-8")
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == []


def test_proto_022_fail_when_go_server_defines_no_detectable_tool(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "main.go").write_text(
        'package internal\nfunc run() { s := mcp.NewServer("x", nil); _ = s }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-022") is not None


def test_proto_022_pass_when_go_server_registers_through_mcp_go(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "main.go").write_text(
        "package internal\nfunc run() {\n"
        '\ts := server.NewMCPServer("x", "1.0")\n'
        '\ts.AddTool(mcp.NewTool("x_search"), handle)\n}\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-022") is None


def test_proto_022_ignores_a_server_accessor_call(tmp_path: Path) -> None:
    # `cfg.Server()` is an accessor, not a construction; treating it as one
    # fails a toolless library with evidence reading "server constructed".
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        "def endpoint(cfg):\n    return cfg.Server()\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-022") is None


def test_proto_022_ignores_registrations_in_a_vendored_tree(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "main.go").write_text(
        'package internal\nfunc run() { s := mcp.NewServer("x", nil); _ = s }\n',
        encoding="utf-8",
    )
    (tmp_path / "vendor" / "dep").mkdir(parents=True)
    (tmp_path / "vendor" / "dep" / "tools.go").write_text(
        'package dep\nfunc r(s *server.MCPServer) { s.AddTool(mcp.NewTool("dep_search"), h) }\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == []
    assert _check(tmp_path, "go", "PROTO-022") is not None


def test_go_tool_literal_brace_inside_a_description_does_not_end_the_literal(
    tmp_path: Path,
) -> None:
    # Literals are kept by design, so brace counting has to ignore braces inside
    # them or the Name field lands outside the extracted region.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc register(s *mcp.Server) {\n"
        "\taddTool(s, &mcp.Tool{\n"
        '\t\tDescription: "Close the session }",\n'
        '\t\tName:        "good_go_close",\n\t}, handle)\n}\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["good_go_close"]


def test_factory_behind_a_version_guard_is_still_collected(tmp_path: Path) -> None:
    # Reading only tree.body missed a factory declared under a module-level if,
    # and every tool it decorated vanished with it.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "_helpers.py").write_text(
        "import sys\n\nif sys.version_info >= (3, 12):\n"
        "    def good_python_tool(mcp, **kw):\n"
        "        def decorator(fn):\n"
        "            return mcp.tool(**kw)(fn)\n"
        "        return decorator\n",
        encoding="utf-8",
    )
    (pkg / "tools.py").write_text(
        "from good_python._helpers import good_python_tool\n\n@good_python_tool(mcp)\n"
        "async def good_python_list(): pass\n",
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == ["good_python_list"]


def test_proto_022_reports_python_source_it_cannot_parse(tmp_path: Path) -> None:
    # A dropped file is invisible to every Python tool rule, and one parseable
    # tool elsewhere used to suppress the only rule that could say so.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        '@mcp.tool()\nasync def good_python_ok() -> str:\n    """Do it.\n\n'
        '    Returns:\n        A thing.\n    """\n    return "x"\n',
        encoding="utf-8",
    )
    (pkg / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    evidence = _check(tmp_path, "python", "PROTO-022")
    assert evidence is not None
    assert "broken.py" in evidence


def test_proto_022_reports_python_source_with_a_nul_byte(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "binary.py").write_bytes(b"x = 1\x00\n")
    evidence = _check(tmp_path, "python", "PROTO-022")
    assert evidence is not None
    assert "binary.py" in evidence


def test_proto_022_detects_the_low_level_python_sdk_server(tmp_path: Path) -> None:
    # `Server(name=...)` and `Server(SETTINGS.name)` are the common spellings;
    # requiring a literal first argument missed both.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('app = Server(name="good-python")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-022") is not None

    (pkg / "server.py").write_text("app = Server(SETTINGS.name)\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-022") is not None


def test_proto_022_fail_when_server_defines_no_detectable_tool(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('mcp = FastMCP("good-python")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-022") is not None


def test_go_tool_name_with_non_word_characters_is_still_graded(tmp_path: Path) -> None:
    # An anchored [a-zA-Z0-9_]+ capture dropped the name entirely, so PROTO-001
    # passed on exactly the names it exists to catch.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        'package internal\nfunc R(s *server.MCPServer) { s.AddTool(mcp.NewTool("Bad-Name"), h) }\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["Bad-Name"]
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_go_tool_literal_name_with_a_space_is_still_graded(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        'package internal\nfunc R() { addTool(s, &mcp.Tool{Name: "Bad Name"}, h) }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_go_unreadable_name_field_does_not_fall_back_to_a_nested_literal(
    tmp_path: Path,
) -> None:
    # `Name: toolName` names one tool the auditor cannot read. Recursing into the
    # nested literal graded an internal id as if it were the tool name.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\nfunc R() {\n"
        '\taddTool(s, &mcp.Tool{Name: toolName, Meta: &mcp.Meta{Name: "internal_id"}}, h)\n}\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == []


def test_python_tool_graded_on_its_registered_name_not_the_def(tmp_path: Path) -> None:
    # @mcp.tool(name=...) publishes that string; grading the def name let a
    # non-conforming registered name pass because the def beside it was fine.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(name="Bad-Name")\ndef good_python_search(q: str) -> str:\n    return q\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == ["Bad-Name"]
    assert _check(repo_root, "python", "PROTO-001") is not None


def test_python_tool_name_ignores_a_co_located_non_tool_decorator(tmp_path: Path) -> None:
    # A stacked CLI decorator carries its own name= — kebab-case by convention.
    # Reading it as the tool name failed a conforming tool, and with the
    # decorators in the other order it hid the name that actually registers.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@app.command(name="get-devices")\n@mcp.tool()\n'
        "def good_python_search(q: str) -> str:\n    return q\n",
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == ["good_python_search"]
    assert _check(repo_root, "python", "PROTO-001") is None


def test_python_tool_name_read_from_a_repo_decorator_factory(tmp_path: Path) -> None:
    # A repo's own factory forwards its kwargs to mcp.tool, so its name= is the
    # registered name just as the tool decorator's is.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "def good_python_tool(**kw):\n"
        "    def decorator(fn):\n"
        "        return mcp.tool(**kw)(fn)\n"
        "    return decorator\n\n"
        '@good_python_tool(name="Bad-Name")\n'
        "def good_python_search(q: str) -> str:\n    return q\n",
        encoding="utf-8",
    )
    repo = Repo(name="good_python", path=repo_root, language="python", github_slug="x/y")
    assert _tool_names(repo) == ["Bad-Name"]


def test_go_with_tools_does_not_capture_past_the_call(tmp_path: Path) -> None:
    # A variadic WithTools( has no literal of its own. A window bounded only by
    # the next comma left the call and graded a later quoted span as a tool name,
    # which also suppressed PROTO-022's report that the tool surface is unread.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        "package internal\n"
        "func R(s *server.MCPServer) {\n"
        "\ts.AddTools(server.WithTools(tools...))\n"
        '\tlog.Printf("failed: %v", err)\n'
        '\tother := "tail"\n}\n'
        'func N() { srv := server.NewMCPServer("x", "1") }\n',
        encoding="utf-8",
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == []
    assert _check(tmp_path, "go", "PROTO-022") is not None


def test_go_with_tools_name_is_still_graded(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        'package internal\nvar _ = WithTools("Bad-Name")\n', encoding="utf-8"
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == ["Bad-Name"]
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_go_empty_tool_name_is_graded_not_an_error(tmp_path: Path) -> None:
    # The widened capture can match nothing at all; a truthiness test on the
    # group raised StopIteration, which audit.py records as an error finding.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "reg.go").write_text(
        'package internal\nvar _ = WithTools("")\n', encoding="utf-8"
    )
    repo = Repo(name="good_go", path=tmp_path, language="go", github_slug="x/y")
    assert _tool_names(repo) == [""]
    assert _check(tmp_path, "go", "PROTO-001") is not None


def test_proto_022_ignores_a_constructor_named_inside_a_string(tmp_path: Path) -> None:
    # A client library that merely mentions FastMCP in an error message failed a
    # MUST with evidence reading "server constructed".
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text(
        'def go():\n    raise RuntimeError("FastMCP(...) not initialised")\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-022") is None


def test_proto_022_still_sees_a_real_construction_after_literal_masking(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('app = Server("good-python")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-022") is not None


def test_proto_022_pass_when_repo_constructs_no_server(tmp_path: Path) -> None:
    # A client or library has no tool surface to audit, so there is nothing to
    # pass vacuously.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "client.py").write_text("def fetch(url):\n    return url\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-022") is None


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


def test_proto_005_006_gate_recognise_same_flag(tmp_path: Path) -> None:
    # The split (PROTO-005) and gate (PROTO-006) checks must accept the same
    # flag spellings; an ``allowwrites`` env flag used to clear the split but
    # not the gate. The body deliberately avoids register_read/register_write so
    # PROTO-005 cannot pass via its structural fallback.
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "if os.environ.get('ALLOWWRITES'):\n    register_tools(mcp)\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-005") is None
    assert _check(tmp_path, "python", "PROTO-006") is None


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


def test_proto_013_pass_when_os_stdout_is_injected(tmp_path: Path) -> None:
    # Passing os.Stdout as an argument is dependency injection (the CLI hands it
    # to a run() that serves the stdio protocol), not a write that corrupts the
    # stream. It must not trip PROTO-013.
    (tmp_path / "cmd" / "srv").mkdir(parents=True)
    (tmp_path / "cmd" / "srv" / "main.go").write_text(
        'package main\nimport "os"\n'
        "func main() { _ = run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr) }\n"
        "func run(...any) error { return nil }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is None


def test_proto_013_fail_on_go_fprintln_to_stdout(tmp_path: Path) -> None:
    # An explicit fmt.Fprintln(os.Stdout, …) IS a real write to the protocol
    # stream, unlike fmt.Fprintln to an injected writer.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        'package internal\nimport ("fmt"; "os")\nfunc Boot() { fmt.Fprintln(os.Stdout, "up") }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_os_stdout_write(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        'package internal\nimport "os"\nfunc Boot() { _, _ = os.Stdout.Write([]byte("up")) }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_io_copy_into_stdout(tmp_path: Path) -> None:
    # os.Stdout handed to a copying writer is a write, not injection: the bytes
    # land on the protocol stream just the same.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "dump.go").write_text(
        'package internal\nimport ("io"; "os")\n'
        "func Dump(r io.Reader) { _, _ = io.Copy(os.Stdout, r) }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_bufio_writer_on_stdout(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "buf.go").write_text(
        'package internal\nimport ("bufio"; "os")\n'
        "func Boot() { w := bufio.NewWriter(os.Stdout); _ = w }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_io_writestring_to_stdout(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "note.go").write_text(
        'package internal\nimport ("io"; "os")\n'
        'func Boot() { _, _ = io.WriteString(os.Stdout, "up") }\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_json_encoder_on_stdout(tmp_path: Path) -> None:
    # The idiomatic Go way to emit structured output, and the one most likely to
    # interleave with JSON-RPC frames.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "emit.go").write_text(
        'package internal\nimport ("encoding/json"; "os")\n'
        "func Emit(v any) { _ = json.NewEncoder(os.Stdout).Encode(v) }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_sized_bufio_writer_on_stdout(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "sized.go").write_text(
        'package internal\nimport ("bufio"; "os")\n'
        "func Boot() { w := bufio.NewWriterSize(os.Stdout, 4096); _ = w }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_multiwriter_fanning_out_to_stdout(tmp_path: Path) -> None:
    # io.MultiWriter is the one sink where every argument is a destination, so a
    # trailing os.Stdout still lands on the frame stream.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "tee.go").write_text(
        'package internal\nimport ("io"; "os")\n'
        "func Tee(logFile io.Writer) { w := io.MultiWriter(logFile, os.Stdout); _ = w }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_multiwriter_with_stdout_after_a_nested_call(tmp_path: Path) -> None:
    # A call expression in an earlier argument closes a paren mid-list, which is
    # why the argument list is extracted with balanced matching rather than a
    # negated character class.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "tee2.go").write_text(
        'package internal\nimport ("bufio"; "io"; "os")\n'
        "func Tee(f io.Writer) { w := io.MultiWriter(bufio.NewWriter(f), os.Stdout); _ = w }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_fail_on_go_multiwriter_with_stdout_first(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "tee3.go").write_text(
        'package internal\nimport ("io"; "os")\n'
        "func Tee(f io.Writer) { w := io.MultiWriter(os.Stdout, f); _ = w }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is not None


def test_proto_013_pass_when_stdout_is_not_the_destination_writer(tmp_path: Path) -> None:
    # Only the first argument is the destination. os.Stdout as a copy *source*,
    # and a writer built over an injected `out`, leave the frame stream alone —
    # matching os.Stdout in any argument position would resurrect the false
    # positives the narrower heuristic exists to avoid.
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "relay.go").write_text(
        'package internal\nimport ("bufio"; "io"; "os")\n'
        "func Relay(w io.Writer, out io.Writer) {\n"
        "\t_, _ = io.Copy(w, os.Stdout)\n"
        "\tb := bufio.NewWriter(out)\n\t_ = b\n}\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-013") is None


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


def test_proto_018_fail_on_overlong_tool_name(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    long_name = "good_python_" + "x" * 60  # 72 chars, over the 64 limit
    (pkg / "tools.py").write_text(f"@mcp.tool\ndef {long_name}(): pass\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-018") is not None


def test_proto_018_pass_on_short_tool_name(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text("@mcp.tool\ndef good_python_list(): pass\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-018") is None


def test_proto_019_pass_with_fastmcp_instructions(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text(
        'mcp = FastMCP("good-python", instructions="Search before get.")\n', encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-019") is None


def test_proto_019_pass_with_go_with_instructions(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        'package internal\nvar _ = server.WithInstructions("Search before get.")\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-019") is None


def test_proto_019_fail_when_instructions_absent(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text('mcp = FastMCP("good-python")\n', encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-019") is not None


def test_proto_020_pass_with_tool_title(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(annotations={"title": "List things"})\n'
        "def good_python_list(x: int) -> str:\n    return ''\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-020") is None


def test_proto_020_fail_when_tool_has_no_title(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef good_python_list(x: int) -> str:\n    return ''\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-020") is not None


def test_proto_020_pass_when_no_tools_defined(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "server.py").write_text("mcp = FastMCP('good-python')\n", encoding="utf-8")
    assert _check(tmp_path, "python", "PROTO-020") is None


def test_proto_021_fail_on_unguarded_elicit(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "async def good_python_confirm(ctx):\n    return await ctx.elicit('Sure?')\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-021") is not None


def test_proto_021_pass_when_capability_checked(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "from fastmcp.exceptions import CapabilityNotSupported\n"
        "async def good_python_confirm(ctx):\n"
        "    try:\n        return await ctx.elicit('Sure?')\n"
        "    except CapabilityNotSupported:\n        return 'ask the user'\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-021") is None


def test_proto_021_pass_when_no_elicit_or_sample(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef good_python_list(x: int) -> str:\n    return ''\n", encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-021") is None


def test_proto_021_fail_on_unguarded_go_sampling(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        "package internal\nfunc summarize() { _, _ = srv.CreateMessage(req) }\n",
        encoding="utf-8",
    )
    assert _check(tmp_path, "go", "PROTO-021") is not None


def test_proto_002_detects_multiline_nested_annotation(tmp_path: Path) -> None:
    # More than one level of paren nesting inside a decorator that spans lines
    # used to defeat the matcher, hiding the tool from every PROTO-* check.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool(\n    annotations=ToolAnnotations(readOnlyHint=bool(1)),\n)\n"
        "def list_things(): pass\n",
        encoding="utf-8",
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_002_detects_multiline_decorator_string_with_paren(tmp_path: Path) -> None:
    # A ``)`` inside a decorator string literal used to unbalance the matcher.
    repo_root = tmp_path / "good_python"
    pkg = repo_root / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(\n    name="emoji :) ",\n)\ndef list_things(): pass\n',
        encoding="utf-8",
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_015_fail_on_multiline_nested_annotation_without_description(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        "@mcp.tool(\n    annotations=ToolAnnotations(readOnlyHint=bool(1)),\n)\n"
        'def good_python_list(x: int) -> str:\n    return ""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is not None


def test_proto_015_pass_with_paren_in_description_string(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "tools.py").write_text(
        '@mcp.tool(\n    description="List things (all of them)",\n)\n'
        'def good_python_list(x: int) -> str:\n    return ""\n',
        encoding="utf-8",
    )
    assert _check(tmp_path, "python", "PROTO-015") is None


def _py_source(root: Path, body: str) -> Path:
    pkg = root / "src" / "good_python"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "protocol.py").write_text(body, encoding="utf-8")
    return root


def test_proto_023_pass_on_discover_method_string(tmp_path: Path) -> None:
    _py_source(tmp_path, 'DISCOVER = "server/discover"\n')
    assert _check(tmp_path, "python", "PROTO-023") is None


def test_proto_023_fail_when_absent(tmp_path: Path) -> None:
    _py_source(tmp_path, "x = 1\n")
    assert _check(tmp_path, "python", "PROTO-023") is not None


def test_proto_023_ignores_a_mention_in_a_comment(tmp_path: Path) -> None:
    _py_source(tmp_path, "# TODO: answer server/discover once fastmcp ships it\nx = 1\n")
    assert _check(tmp_path, "python", "PROTO-023") is not None


def test_proto_023_pass_on_go_identifier(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "srv.go").write_text(
        "package internal\nfunc ServerDiscover() {}\n", encoding="utf-8"
    )
    assert _check(tmp_path, "go", "PROTO-023") is None


def test_proto_024_pass_on_camel_and_snake_spellings(tmp_path: Path) -> None:
    for body in ('R = {"resultType": "tool_result"}\n', "result_type = 'tool_result'\n"):
        _py_source(tmp_path, body)
        assert _check(tmp_path, "python", "PROTO-024") is None


def test_proto_024_fail_when_absent(tmp_path: Path) -> None:
    _py_source(tmp_path, "R = {'content': []}\n")
    assert _check(tmp_path, "python", "PROTO-024") is not None


def test_proto_025_fail_names_the_missing_hint(tmp_path: Path) -> None:
    _py_source(tmp_path, 'R = {"ttlMs": 1000}\n')
    evidence = _check(tmp_path, "python", "PROTO-025")
    assert evidence is not None
    assert "cacheScope" in evidence
    assert "ttlMs" not in evidence


def test_proto_025_pass_with_both_hints(tmp_path: Path) -> None:
    _py_source(tmp_path, 'R = {"ttlMs": 1000, "cacheScope": "session"}\n')
    assert _check(tmp_path, "python", "PROTO-025") is None


def test_proto_026_fail_on_retired_code(tmp_path: Path) -> None:
    _py_source(tmp_path, "RESOURCE_NOT_FOUND = -32002\n")
    assert _check(tmp_path, "python", "PROTO-026") is not None


def test_proto_026_pass_on_current_code(tmp_path: Path) -> None:
    _py_source(tmp_path, "RESOURCE_NOT_FOUND = -32602\n")
    assert _check(tmp_path, "python", "PROTO-026") is None


def test_proto_026_ignores_the_code_named_in_a_comment(tmp_path: Path) -> None:
    # Migration notes cite the old code; only a live constant is a violation.
    _py_source(tmp_path, "# was -32002 before the 2026-07-28 revision\nCODE = -32602\n")
    assert _check(tmp_path, "python", "PROTO-026") is None


def test_proto_023_counts_a_method_string_literal(tmp_path: Path) -> None:
    # The method name is a literal on the wire, so literals must count.
    _py_source(tmp_path, 'HANDLERS = {"server/discover": _discover}\n')
    assert _check(tmp_path, "python", "PROTO-023") is None


def test_proto_023_matches_camel_case_identifier(tmp_path: Path) -> None:
    _py_source(tmp_path, "def serverDiscover():\n    return {}\n")
    assert _check(tmp_path, "python", "PROTO-023") is None


def test_proto_023_fail_on_a_longer_word_starting_with_the_marker(tmp_path: Path) -> None:
    _py_source(tmp_path, "server_discovery_cache = {}\n")
    assert _check(tmp_path, "python", "PROTO-023") is not None


def test_proto_024_ignores_a_mention_in_a_comment(tmp_path: Path) -> None:
    _py_source(tmp_path, "# resultType lands once the SDK ships it\nR = {}\n")
    assert _check(tmp_path, "python", "PROTO-024") is not None


def test_proto_025_fail_names_both_missing_hints(tmp_path: Path) -> None:
    _py_source(tmp_path, "R = {}\n")
    evidence = _check(tmp_path, "python", "PROTO-025")
    assert evidence is not None
    assert "ttlMs" in evidence
    assert "cacheScope" in evidence


def test_proto_026_ignores_the_code_named_in_a_string_literal(tmp_path: Path) -> None:
    # A migration note in an error message names the code it forbids; reading it
    # as a use of the code fails the repo that has already migrated.
    _py_source(tmp_path, 'CODE = -32602\nMSG = "do not return -32002"\n')
    assert _check(tmp_path, "python", "PROTO-026") is None


def test_proto_026_ignores_a_subtraction(tmp_path: Path) -> None:
    # Formatted subtraction spaces the operator; the sign must sit against the
    # digits to read as the error code.
    _py_source(tmp_path, "offset = base - 32002\n")
    assert _check(tmp_path, "python", "PROTO-026") is None


def test_proto_026_ignores_digits_inside_an_identifier(tmp_path: Path) -> None:
    _py_source(tmp_path, "sku_32002 = 1\n")
    assert _check(tmp_path, "python", "PROTO-026") is None


def test_proto_026_fail_on_a_go_constant(tmp_path: Path) -> None:
    (tmp_path / "internal").mkdir(parents=True)
    (tmp_path / "internal" / "errs.go").write_text(
        "package internal\n\nconst resourceNotFound = -32002\n", encoding="utf-8"
    )
    assert _check(tmp_path, "go", "PROTO-026") is not None
