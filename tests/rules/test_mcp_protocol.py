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
    (pkg / "tools.py").write_text(
        "@mcp.tool\ndef list_things(): pass\n", encoding="utf-8"
    )
    assert _check(repo_root, "python", "PROTO-002") is not None


def test_proto_011_fail_on_token_cli_arg(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "good_python"
    pkg.mkdir(parents=True)
    (pkg / "__main__.py").write_text(
        'parser.add_argument("--api-key")\n', encoding="utf-8"
    )
    assert _check(tmp_path, "python", "PROTO-011") is not None
