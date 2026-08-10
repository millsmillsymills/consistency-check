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
    strip_block_comments,
)
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A `/*` written in prose on a `//` line must not open a span. It did,
        # and every registration after it vanished from the audit.
        ("// see /* here\nvar b = 1\n", "// see /* here\nvar b = 1\n"),
        # Same failure via a lone apostrophe read as a rune literal.
        ("// don't\n/* real */\nvar b = 1\n", "// don't\n\nvar b = 1\n"),
        # A `/*` inside a literal is data, not a comment.
        ('const u = "https://x/*/y"\nvar b = 1\n', 'const u = "https://x/*/y"\nvar b = 1\n'),
        ("var a = `raw /* text`\nvar b = 1\n", "var a = `raw /* text`\nvar b = 1\n"),
        ("var q = '\"'\nvar b = 1\n", "var q = '\"'\nvar b = 1\n"),
        ("var a = 1 /* c */ + 2\n", "var a = 1  + 2\n"),
        # Go treats an unterminated block comment as running to EOF.
        ("var a = 1\n/* never closed\nvar b = 2\n", "var a = 1\n\n\n"),
    ],
)
def test_strip_block_comments(text: str, expected: str) -> None:
    assert strip_block_comments(text) == expected


def test_go_block_comments_are_stripped_by_both_entry_points() -> None:
    go = 'package p\n/* os.Stdout.Write(b) */\nvar u = "x"\n'
    assert "os.Stdout" not in code_only(go, "//")
    assert "os.Stdout" not in code_and_literals(go, "//")
    # code_and_literals keeps literals; code_only drops them.
    assert '"x"' in code_and_literals(go, "//")


def test_quote_inside_a_block_comment_does_not_erase_the_file() -> None:
    # STRING_LITERAL is comment-blind: run before block-comment stripping it
    # consumed the comment's own terminator, and the unterminated /* that was
    # left deleted every line below. An empty file passes every check.
    # Two quotes are needed — one in the comment, one in real code below — or
    # STRING_LITERAL never pairs and the ordering is not exercised.
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
    # _BLOCK_STRING pairs the two `"""` written in prose unless comments go
    # first, taking the FastMCP construction between them with it.
    py = '# a docstring is delimited by """\nmcp = FastMCP("foo")\n# close the """ too\n'
    assert "FastMCP" in code_and_literals(py, "#")


def test_python_docstrings_are_still_stripped() -> None:
    py = 'def f():\n    """Do it.\n\n    print("not a call")\n    """\n    return 1\n'
    assert "not a call" not in code_and_literals(py, "#")


def test_go_raw_string_triple_quotes_do_not_span_files() -> None:
    # _BLOCK_STRING is a Python docstring pattern. Applied to Go it paired two
    # unrelated `"""` sequences and deleted the registration between them.
    go = 'package t\nconst a = `ex: """`\nfunc r() { s.AddTool(mcp.NewTool("x_go"), h) }\n'
    assert "AddTool" in code_and_literals(go, "//")


def test_combined_code_text_scrubs_each_file_before_joining(tmp_path: Path) -> None:
    # An unclosed docstring used to pair with a `\"\"\"` in another file and
    # consume everything between them, because the scrub ran over the
    # concatenation rather than over each file. Each file here opens a docstring
    # it never closes and then names itself, so whichever order the walk
    # returns, a join-then-scrub eats one of the two names.
    pkg = tmp_path / "src" / "u"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text('q = """A\nmcp = FastMCP("alpha")\n', encoding="utf-8")
    (pkg / "b.py").write_text('q = """B\nmcp = FastMCP("beta")\n', encoding="utf-8")
    repo = Repo(name="u", path=tmp_path, language="python", github_slug="x/y")
    text = combined_code_text(repo)
    assert "alpha" in text
    assert "beta" in text


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
