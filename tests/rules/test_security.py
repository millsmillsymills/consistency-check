"""Tests for security rules."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from consistency_check.rules.security import RULES
from consistency_check.types import NotApplicable, Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, rid: str) -> str | None | NotApplicable:
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


def test_mcp_019_skips_gitignored_env_when_repo_is_git(
    good_python_repo: Path,
) -> None:
    (good_python_repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    gi = good_python_repo / ".gitignore"
    gi.write_text(gi.read_text() + ".env\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=good_python_repo, check=True)
    subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=good_python_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=good_python_repo,
        check=True,
    )
    assert _check(good_python_repo, "MCP-019") is None


def test_mcp_019_flags_committed_env(good_python_repo: Path) -> None:
    env = good_python_repo / ".env"
    env.write_text("TOKEN=secret\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=good_python_repo, check=True)
    subprocess.run(["git", "add", ".env", "README.md"], cwd=good_python_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=good_python_repo,
        check=True,
    )
    evidence = _check(good_python_repo, "MCP-019")
    assert isinstance(evidence, str)
    assert ".env" in evidence
