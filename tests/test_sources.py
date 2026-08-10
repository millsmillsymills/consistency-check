"""Tests for source-text discovery and comment stripping."""

from __future__ import annotations

import pytest
from consistency_check.sources import code_and_literals, code_only, strip_block_comments


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


def test_python_slash_star_is_not_a_comment() -> None:
    # `/*` carries no meaning in Python; stripping it there would eat real code.
    py = 'x = 1 /* 2\nprint("kept")\n'
    assert "kept" in code_and_literals(py, "#")
