"""Tests for source-text discovery and comment stripping."""

from __future__ import annotations

import pytest
from consistency_check.sources import (
    code_and_literals,
    code_only,
    mask_literal_braces,
    strip_block_comments,
)


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
    go = 'package main\n\n/* helper for the " character */\n\nvar c = &http.Client{}\n'
    assert "http.Client" in code_only(go, "//")
    assert "helper" not in code_only(go, "//")


def test_go_raw_string_triple_quotes_do_not_span_files() -> None:
    # _BLOCK_STRING is a Python docstring pattern. Applied to Go it paired two
    # unrelated `"""` sequences and deleted the registration between them.
    go = 'package t\nconst a = `ex: """`\nfunc r() { s.AddTool(mcp.NewTool("x_go"), h) }\n'
    assert "AddTool" in code_and_literals(go, "//")


def test_mask_literal_braces_only_touches_literals() -> None:
    assert mask_literal_braces('a{ x = "}" }') == 'a{ x = " " }'


def test_python_slash_star_is_not_a_comment() -> None:
    # `/*` carries no meaning in Python; stripping it there would eat real code.
    py = 'x = 1 /* 2\nprint("kept")\n'
    assert "kept" in code_and_literals(py, "#")
