"""Tests for security rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.security import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="python", github_slug="x/y"),
    )


def test_mcp_019_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "MCP-019") is None


def test_mcp_019_fail_on_env_file(good_python_repo: Path) -> None:
    (good_python_repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-019") is not None


def test_mcp_020_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "MCP-020") is None


def test_mcp_020_fail_on_empty_security_md(good_python_repo: Path) -> None:
    (good_python_repo / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-020") is not None


def test_mcp_019_skips_pem_inside_venv(good_python_repo: Path) -> None:
    venv_certs = good_python_repo / ".venv" / "lib" / "python3.13" / "site-packages" / "certifi"
    venv_certs.mkdir(parents=True)
    (venv_certs / "cacert.pem").write_text("-----BEGIN CERT-----\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-019") is None


def test_mcp_019_skips_env_inside_node_modules(good_python_repo: Path) -> None:
    nm = good_python_repo / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / ".env").write_text("X=y\n", encoding="utf-8")
    assert _check(good_python_repo, "MCP-019") is None
