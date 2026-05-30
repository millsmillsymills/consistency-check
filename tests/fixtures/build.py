"""Construct synthetic MCP repos for rule-module tests."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(content).lstrip(), encoding="utf-8")


def build_good_python(root: Path) -> Path:
    """Create a Python repo skeleton that satisfies every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)

    _write(
        root / "README.md",
        """
        # good-python

        ## Status
        Alpha.

        ## Quick Start
        Install: ``pip install good-python``.

        ## Configuration
        Set GOOD_TOKEN.

        ## Development
        ``uv sync --all-groups``. Use Claude Desktop to test.

        ## License
        Apache-2.0.
    """,
    )

    _write(root / "LICENSE", "Apache License 2.0\nCopyright (c) good-python contributors\n")
    _write(root / "SECURITY.md", "## Reporting\nEmail security@example.com.\n")
    _write(root / "CHANGELOG.md", "## [Unreleased]\n- Initial.\n")
    _write(root / "CONTRIBUTING.md", "## How to contribute\nRun ``prek install``.\n")
    _write(root / "CLAUDE.md", "See ~/Projects/consistency-check/docs/standards/.\n")
    _write(root / ".gitignore", "__pycache__/\n*.pyc\n.venv/\n")

    _write(
        root / "pyproject.toml",
        """
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "good-python"
        version = "0.1.0"
        license = "Apache-2.0"
        requires-python = ">=3.13"
        dependencies = ["fastmcp>=3.0,<4", "httpx", "tenacity"]

        [dependency-groups]
        dev = ["pytest", "pytest-asyncio", "ruff", "ty", "hypothesis"]

        [tool.ruff]
        target-version = "py313"
        line-length = 100
    """,
    )

    _write(root / "uv.lock", "# placeholder lockfile\n")
    _write(root / ".pre-commit-config.yaml", "repos: []\n")

    pkg = root / "src" / "good_python"
    _write(pkg / "__init__.py", '"""good-python package."""\n')
    _write(pkg / "py.typed", "")
    _write(
        pkg / "server.py",
        """
        from __future__ import annotations
        from dataclasses import dataclass
        from fastmcp import FastMCP

        @dataclass
        class ServerContext:
            pass

        mcp = FastMCP("good-python")
    """,
    )
    _write(pkg / "config.py", "from __future__ import annotations\n")
    _write(
        pkg / "errors.py",
        """
        from __future__ import annotations

        class GoodPythonError(Exception):
            pass
    """,
    )
    _write(
        pkg / "__main__.py",
        """
        from __future__ import annotations
        import sys, logging
        logging.basicConfig(stream=sys.stderr)
    """,
    )
    _write(pkg / "clients" / "__init__.py", "")
    _write(pkg / "tools" / "__init__.py", "")

    _write(root / "tests" / "conftest.py", "import pytest\n\n@pytest.fixture\ndef x(): return 1\n")
    _write(root / "tests" / "unit" / "test_smoke.py", "def test_smoke(): assert True\n")
    _write(root / "tests" / "integration" / ".keep", "")
    _write(
        root / "tests" / "property" / "test_props.py",
        "from hypothesis import given, strategies as st\n"
        "@given(st.integers())\ndef test_id(n): assert n == n\n",
    )

    _write(
        root / ".github" / "workflows" / "ci.yml",
        """
        name: ci
        on:
          push: {}
          pull_request: {}
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7
              - run: uv run ruff check .
              - run: uv run pytest -q
    """,
    )
    _write(root / ".github" / "workflows" / "security.yml", "name: security\non: schedule\n")
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")

    return root


def build_bad_python(root: Path) -> Path:
    """Create a Python repo skeleton that fails every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-python\n")
    return root


def build_good_go(root: Path) -> Path:
    """Create a Go repo skeleton that satisfies every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)

    _write(
        root / "README.md",
        """
        # good-go

        ## Status
        Alpha.

        ## Install
        ``go install`` it.

        ## Environment variables
        GOOD_TOKEN.

        ## Development
        Use Claude Desktop.

        ## License
        Apache-2.0.
    """,
    )

    _write(root / "LICENSE", "Apache License 2.0\nCopyright good-go.\n")
    _write(root / "SECURITY.md", "## Reporting\nUse GitHub Security Advisories.\n")
    _write(root / "CHANGELOG.md", "## [Unreleased]\n")
    _write(root / "CONTRIBUTING.md", "## How to contribute\n")
    _write(root / "CLAUDE.md", "See ~/Projects/consistency-check/docs/standards/.\n")
    _write(root / ".gitignore", "*.test\n*.out\n")
    _write(
        root / "go.mod",
        "module github.com/example/good-go\ngo 1.22\n\n"
        "require github.com/mark3labs/mcp-go v0.1.0\n",
    )
    _write(root / "go.sum", "")
    _write(
        root / ".golangci.yml",
        """
        linters:
          enable:
            - errcheck
            - govet
            - staticcheck
            - unused
            - gocritic
    """,
    )
    _write(
        root / "cmd" / "good-go" / "main.go",
        """
        package main

        import (
            "log/slog"
            "os"
        )

        func main() {
            slog.New(slog.NewJSONHandler(os.Stderr, nil))
        }
    """,
    )
    _write(
        root / "internal" / "tools" / "tools.go",
        """
        package tools
        import "context"
        func GetThing(ctx context.Context) error { return nil }
    """,
    )
    _write(
        root / "internal" / "tools" / "tools_test.go",
        """
        package tools
        import "testing"
        func TestGet(t *testing.T) {
            tests := []struct{ name string }{{"a"}}
            for _, tt := range tests { _ = tt.name }
        }
    """,
    )
    _write(root / "integration" / "smoke_test.go", "package integration\n")

    _write(
        root / ".github" / "workflows" / "ci.yml",
        """
        name: ci
        on:
          push: {}
          pull_request: {}
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@e2f20e631ae6d7dd3b768f56a5d2af784dd54791  # v4.1.7
              - run: gofmt -d .
              - run: go test ./... -race -count=1
    """,
    )
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")
    return root


def build_bad_go(root: Path) -> Path:
    """Create a Go repo skeleton that fails every applicable rule."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-go\n")
    return root
