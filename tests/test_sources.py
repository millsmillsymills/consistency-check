"""Tests for source-text discovery and comment stripping."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.sources import (
    code_and_literals,
    code_only,
    combined_code_text,
    go_sources,
    mask_literal_braces,
    mask_literal_contents,
    strip_go_comments,
    strip_go_literals,
    strip_python_literals,
)
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A `/*` written in prose on a `//` line must not open a span. It did,
        # and every registration after it vanished from the audit.
        ("// see /* here\nvar b = 1\n", "\nvar b = 1\n"),
        # Same failure via a lone apostrophe read as a rune literal.
        ("// don't\n/* real */\nvar b = 1\n", "\n\nvar b = 1\n"),
        # A `/*` inside a literal is data, not a comment.
        ('const u = "https://x/*/y"\nvar b = 1\n', 'const u = "https://x/*/y"\nvar b = 1\n'),
        ("var a = `raw /* text`\nvar b = 1\n", "var a = `raw /* text`\nvar b = 1\n"),
        ("var q = '\"'\nvar b = 1\n", "var q = '\"'\nvar b = 1\n"),
        ("var a = 1 /* c */ + 2\n", "var a = 1  + 2\n"),
        # Go treats an unterminated block comment as running to EOF.
        ("var a = 1\n/* never closed\nvar b = 2\n", "var a = 1\n\n\n"),
        # A `//` inside a literal is data. Dropping it here would take the
        # closing quote with it and leave the literal scanner unterminated.
        ('const u = "http://x"\nvar b = 1\n', 'const u = "http://x"\nvar b = 1\n'),
        # The same, spanning lines: only a raw string can, and its closing line
        # is exactly where a URL tends to sit.
        ("var a = `one\ntwo http://x`\nvar b = 1\n", "var a = `one\ntwo http://x`\nvar b = 1\n"),
        # A trailing comment leaves the code before it and the newline after it.
        ('var a = "x" // note\nvar b = 1\n', 'var a = "x" \nvar b = 1\n'),
        # A `//` comment at EOF with no trailing newline.
        ("var a = 1\n// note", "var a = 1\n"),
    ],
)
def test_strip_go_comments(text: str, expected: str) -> None:
    assert strip_go_comments(text) == expected


def test_go_block_comments_are_stripped_by_both_entry_points() -> None:
    go = 'package p\n/* os.Stdout.Write(b) */\nvar u = "x"\n'
    assert "os.Stdout" not in code_only(go, "//")
    assert "os.Stdout" not in code_and_literals(go, "//")
    # code_and_literals keeps literals; code_only drops them.
    assert '"x"' in code_and_literals(go, "//")


def test_quote_inside_a_block_comment_does_not_erase_the_file() -> None:
    # Comments are recognised before literals. Reversed, a quote inside a block
    # comment consumes the comment's own terminator and the unterminated /* left
    # behind deletes every line below, and an empty file passes every check.
    # Two quotes are needed, one in the comment and one in real code below, or
    # the ordering is not exercised.
    go = 'package main\n/* helper for the " character */\nvar u = "x"\nvar c = &http.Client{}\n'
    assert "http.Client" in code_only(go, "//")
    assert "helper" not in code_only(go, "//")


def test_quote_inside_a_line_comment_does_not_erase_the_file() -> None:
    # Same defect one line down: the line-comment strip also has to run before
    # literals, or an apostrophe in prose pairs with the next quote in code.
    py = "# TODO: the API doesn't page yet\ndef run():\n    return httpx.Client(base_url='u')\n"
    assert "httpx.Client" in code_only(py, "#")
    go = 'package p\n// header must be exactly "application/json\nvar u = "x"\nvar c = 1\n'
    assert "var c = 1" in code_only(go, "//")


def test_python_comments_mentioning_triple_quotes_do_not_erase_code() -> None:
    # A `"""` written in prose is not a docstring opener. Pair the two and the
    # FastMCP construction between them goes with them.
    py = '# a docstring is delimited by """\nmcp = FastMCP("foo")\n# close the """ too\n'
    assert "FastMCP" in code_and_literals(py, "#")


def test_a_docstring_closing_on_a_hash_line_keeps_the_code_after_it() -> None:
    # The Python half of the Go raw-string defect. A per-line comment strip
    # cannot see it is inside a triple-quoted string, so a `#` on the closing
    # line took the closing quotes with it; the orphaned opener then paired with
    # the next docstring in the file and everything between was deleted — here a
    # live -32002, which PROTO-026 then read as absent.
    py = (
        'HELP = """\nUsage: see https://example.com/docs#configuration """\n\n'
        'RETIRED = -32002\n\ndef f():\n    """Docstring."""\n    return httpx.Client()\n'
    )
    out = code_only(py, "#")
    assert "-32002" in out
    assert "httpx.Client" in out
    assert "example.com" not in out
    # code_and_literals drops triple-quoted strings as docstrings, but the code
    # below the malformed one has to survive there too.
    assert "-32002" in code_and_literals(py, "#")


def test_a_hash_inside_a_python_literal_is_not_a_comment() -> None:
    py = 'url = "https://example.com#frag"\nc = httpx.Client()\n'
    assert "httpx.Client" in code_only(py, "#")
    assert "example.com#frag" in code_and_literals(py, "#")


def test_python_docstrings_are_still_stripped() -> None:
    py = 'def f():\n    """Do it.\n\n    print("not a call")\n    """\n    return 1\n'
    assert "not a call" not in code_and_literals(py, "#")


def test_go_raw_string_triple_quotes_do_not_span_files() -> None:
    # Go has no triple-quote form, so two unrelated `"""` sequences must not
    # pair and take the registration between them.
    go = 'package t\nconst a = `ex: """`\nfunc r() { s.AddTool(mcp.NewTool("x_go"), h) }\n'
    assert "AddTool" in code_and_literals(go, "//")


def test_combined_code_text_scrubs_each_file_before_joining(tmp_path: Path) -> None:
    # An unclosed docstring runs to the end of the text it is scanned in, which
    # is the file it appears in and must not be the whole concatenation. Scrubbed
    # over the join, `a.py`'s opener pairs with `b.py`'s and takes every line
    # between them; `b.py` is well-formed and its registration has to survive its
    # neighbour being malformed.
    pkg = tmp_path / "src" / "u"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text('q = """A\nmcp = FastMCP("alpha")\n', encoding="utf-8")
    (pkg / "b.py").write_text('d = """B"""\nmcp = FastMCP("beta")\n', encoding="utf-8")
    repo = Repo(name="u", path=tmp_path, language="python", github_slug="x/y")
    text = combined_code_text(repo)
    assert "beta" in text


def test_a_nested_f_string_quote_does_not_blank_the_file(tmp_path: Path) -> None:
    # PEP 701 lets a replacement field reuse the enclosing quote, so the scanner
    # closes the outer literal early and re-enters on `\"\"\"` that has no closer.
    # Consuming to end of input from there hid every violation below it in a file
    # `ast.parse` accepts — a bypass, not a syntax error.
    pkg = tmp_path / "src" / "u"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text(
        'q = f"{"""x"""}"\nRETIRED = -32002\nmcp = FastMCP("alpha")\n', encoding="utf-8"
    )
    repo = Repo(name="u", path=tmp_path, language="python", github_slug="x/y")
    assert "-32002" in combined_code_text(repo)
    assert "FastMCP" in combined_code_text(repo)


def test_go_sources_ignores_exclusions_in_the_repos_own_ancestors(tmp_path: Path) -> None:
    # p.parts covers every ancestor, so a checkout that merely sat under a
    # directory named `vendor` returned no sources and passed every Go rule.
    root = tmp_path / "vendor" / "thing-mcp"
    (root / "internal").mkdir(parents=True)
    (root / "internal" / "main.go").write_text("package internal\n", encoding="utf-8")
    (root / "vendor" / "dep").mkdir(parents=True)
    (root / "vendor" / "dep" / "d.go").write_text("package dep\n", encoding="utf-8")
    repo = Repo(name="thing-mcp", path=root, language="go", github_slug="x/y")
    assert [p.name for p in go_sources(repo)] == ["main.go"]


def test_mask_literal_braces_only_touches_literals() -> None:
    assert mask_literal_braces('a{ x = "}" }') == 'a{ x = " " }'


def test_python_slash_star_is_not_a_comment() -> None:
    # `/*` carries no meaning in Python; stripping it there would eat real code.
    py = 'x = 1 /* 2\nprint("kept")\n'
    assert "kept" in code_and_literals(py, "#")


def test_mask_literal_contents_keeps_the_call_shape() -> None:
    assert mask_literal_contents('Server("x")') == 'Server("_")'
    assert "FastMCP(" not in mask_literal_contents('raise E("FastMCP( bad")')


def test_quote_does_not_span_lines_except_a_raw_string() -> None:
    # A Go interpreted string or rune cannot contain a newline, so an unbalanced
    # one must not consume the rest of the file.
    assert mask_literal_contents("a = 'unbalanced\nb = 1\n") == "a = '__________\nb = 1\n"
    assert mask_literal_contents("a = `two\nlines`\n") == "a = `___\n_____`\n"


def test_go_raw_string_contents_are_not_read_as_code() -> None:
    # A backtick string is a literal, so its contents are not code.
    go = "package internal\n\nconst doc = `sample error: -32002 was retired`\n"
    assert "-32002" not in code_only(go, "//")


def test_apostrophe_in_a_go_raw_string_does_not_delete_the_next_lines() -> None:
    # The single-quote branch paired the apostrophe with the next one in the
    # file and deleted every line between, including the code being graded.
    go = (
        "package internal\n\nvar H = `don't pass a raw id`\nconst C = -32002\nvar M = `it's fine`\n"
    )
    assert "-32002" in code_only(go, "//")


def test_code_only_keeps_go_code_around_a_dropped_literal() -> None:
    go = 'package internal\n\nfunc F() { log.Print("msg") }\n'
    out = code_only(go, "//")
    assert "log.Print(" in out
    assert "msg" not in out


def test_a_raw_string_closing_on_a_slash_line_keeps_the_code_after_it() -> None:
    # A per-line comment strip cannot see that it is inside a multi-line raw
    # string. Truncating the closing line took the backtick with it, leaving an
    # unterminated raw string that swallowed every remaining line — so a live
    # `-32002` and an `os.Stdout` write both read as absent.
    go = (
        "package p\n\nconst tpl = `line one\nsee http://example.com/docs`\n"
        "const C = -32002\nfunc F() { os.Stdout.Write(b) }\n"
    )
    out = code_only(go, "//")
    assert "-32002" in out
    assert "os.Stdout" in out
    assert "example.com" not in out
    # The same line is why the literal-keeping path must not truncate either.
    assert "example.com" in code_and_literals(go, "//")


def test_an_unterminated_literal_does_not_blank_the_rest_of_the_file() -> None:
    # Consuming to end of input is what Go does with an unterminated raw string,
    # but for an auditor it blanks every violation below the opener and the repo
    # passes. The stray delimiter is treated as an ordinary character instead, so
    # the code after it is still graded.
    # The opener is dropped and its text stays, so `var b = 1` survives. Reading
    # an unterminated literal's prose as code can only produce a false failure,
    # which is the direction an audit is allowed to be wrong in.
    assert strip_go_literals("var a = `open\nvar b = 1\n") == "var a = open\nvar b = 1\n"
    # An unterminated interpreted string already stopped at its newline.
    assert strip_go_literals('var a = "open\nvar b = 1\n') == "var a = \nvar b = 1\n"
    # Python's triple-quoted form is the same shape.
    assert strip_python_literals('q = """open\nb = 1\n') == "q = open\nb = 1\n"


def test_an_escaped_quote_does_not_end_a_go_literal() -> None:
    # Without the escape branch the literal ends at the inner quote and its
    # contents leak into the code text.
    go = 'package p\n\nvar s = "he said \\"os.Stdout\\" once"\n'
    assert "os.Stdout" not in code_only(go, "//")
    assert mask_literal_contents(r'"a\"b"') == '"____"'
