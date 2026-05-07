"""Shared fixtures for rule module tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.fixtures.build import build_bad_go, build_bad_python, build_good_go, build_good_python

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def good_python_repo(tmp_path: Path) -> Path:
    """A synthetic Python MCP repo that satisfies every PY-* and MCP-* rule."""
    return build_good_python(tmp_path / "good_python")


@pytest.fixture
def bad_python_repo(tmp_path: Path) -> Path:
    """A synthetic Python MCP repo that fails every PY-* and MCP-* rule."""
    return build_bad_python(tmp_path / "bad_python")


@pytest.fixture
def good_go_repo(tmp_path: Path) -> Path:
    """A synthetic Go MCP repo that satisfies every GO-* and MCP-* rule."""
    return build_good_go(tmp_path / "good_go")


@pytest.fixture
def bad_go_repo(tmp_path: Path) -> Path:
    """A synthetic Go MCP repo that fails every GO-* and MCP-* rule."""
    return build_bad_go(tmp_path / "bad_go")
