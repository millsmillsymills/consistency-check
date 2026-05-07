"""Tests for PY-* rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.python import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


def _check(p: Path, rid: str) -> str | None:
    return next(r for r in RULES if r.id == rid).check(
        Repo(name="x", path=p, language="python", github_slug="x/y"),
    )


def test_py_001_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "PY-001") is None


def test_py_006_pass(good_python_repo: Path) -> None:
    assert _check(good_python_repo, "PY-006") is None


def test_py_006_fail_when_py_typed_missing(good_python_repo: Path) -> None:
    (good_python_repo / "src" / "good_python" / "py.typed").unlink()
    assert _check(good_python_repo, "PY-006") is not None


def test_py_008_fail_when_mypy_present(good_python_repo: Path) -> None:
    py = good_python_repo / "pyproject.toml"
    text = py.read_text()
    new = text.replace(
        'dev = ["pytest", "pytest-asyncio", "ruff", "ty", "hypothesis"]',
        'dev = ["pytest", "pytest-asyncio", "ruff", "ty", "hypothesis", "mypy"]',
    )
    py.write_text(new, encoding="utf-8")
    assert _check(good_python_repo, "PY-008") is not None


def test_py_015_fail_when_module_lacks_future_import(good_python_repo: Path) -> None:
    server = good_python_repo / "src" / "good_python" / "server.py"
    server.write_text(
        server.read_text().replace("from __future__ import annotations\n", ""),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "PY-015") is not None
