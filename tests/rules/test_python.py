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


def test_py_015_pass_with_long_docstring_before_future_import(good_python_repo: Path) -> None:
    # Regression for the unraid-mcp #171 false positive: a >600-byte
    # module docstring used to push the import out of the read window.
    server = good_python_repo / "src" / "good_python" / "server.py"
    long_doc = '"""' + ("Long contract note. " * 60) + '"""'
    server.write_text(
        long_doc + "\n\nfrom __future__ import annotations\n",
        encoding="utf-8",
    )
    assert _check(good_python_repo, "PY-015") is None


def test_py_017_pass_when_server_makes_no_http_calls(good_python_repo: Path) -> None:
    # Regression for the flipperzero-mcp false positive: a hardware-RPC server
    # that imports no HTTP client is exempt from the httpx mandate.
    py = good_python_repo / "pyproject.toml"
    py.write_text(
        py.read_text().replace('"fastmcp>=3.0,<4", "httpx", "tenacity"', '"fastmcp>=3.0,<4"'),
        encoding="utf-8",
    )
    assert _check(good_python_repo, "PY-017") is None


def test_py_017_fail_when_http_used_without_httpx(good_python_repo: Path) -> None:
    py = good_python_repo / "pyproject.toml"
    py.write_text(
        py.read_text().replace('"fastmcp>=3.0,<4", "httpx", "tenacity"', '"fastmcp>=3.0,<4"'),
        encoding="utf-8",
    )
    client = good_python_repo / "src" / "good_python" / "clients" / "api.py"
    client.write_text("import requests\n", encoding="utf-8")
    assert _check(good_python_repo, "PY-017") is not None


def test_py_019_pass_with_dict_lifespan_yield(good_python_repo: Path) -> None:
    # FastMCP composed lifespans require a plain dict; accept the typed
    # AsyncIterator[dict[str, Any]] yield annotation as an equivalent.
    server = good_python_repo / "src" / "good_python" / "server.py"
    server.write_text(
        "from __future__ import annotations\n"
        "from collections.abc import AsyncIterator\n"
        "from typing import Any\n\n"
        "async def lifespan() -> AsyncIterator[dict[str, Any]]:\n"
        "    yield {}\n",
        encoding="utf-8",
    )
    assert _check(good_python_repo, "PY-019") is None


def test_py_019_fail_when_neither_dataclass_nor_dict_yield(good_python_repo: Path) -> None:
    server = good_python_repo / "src" / "good_python" / "server.py"
    server.write_text(
        "from __future__ import annotations\n\ndef make_server(): return None\n",
        encoding="utf-8",
    )
    assert _check(good_python_repo, "PY-019") is not None
