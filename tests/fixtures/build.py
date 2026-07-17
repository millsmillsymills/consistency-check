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

    _write(
        root / "LICENSE",
        "Apache License\nVersion 2.0, January 2004\nCopyright (c) good-python contributors\n",
    )
    _write(root / "SECURITY.md", "## Reporting\nEmail security@example.com.\n")
    _write(root / "CHANGELOG.md", "## [Unreleased]\n- Initial.\n")
    _write(
        root / "CONTRIBUTING.md",
        "## How to contribute\nRun ``prek install``.\n\n## Release\nTag and push.\n",
    )
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
    _write(
        pkg / "config.py",
        """
        from __future__ import annotations

        # Write tools are gated behind this env flag.
        ENABLE_WRITES = False
    """,
    )
    _write(
        pkg / "errors.py",
        """
        from __future__ import annotations
        from fastmcp.exceptions import ToolError

        class GoodPythonError(Exception):
            pass

        def _classify_error(exc: Exception) -> ToolError:
            return ToolError(str(exc))
    """,
    )
    _write(
        pkg / "__main__.py",
        """
        from __future__ import annotations
        import sys, logging
        import structlog
        logging.basicConfig(stream=sys.stderr)
        _ = structlog
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
              - run: uv run pip-audit
              - run: uv run pytest -q --cov=good_python --cov-fail-under=90
    """,
    )
    _write(root / ".github" / "workflows" / "security.yml", "name: security\non: schedule\n")
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")

    return root


def build_bad_python(root: Path) -> Path:
    """Create a Python repo that fails every applicable rule it can.

    Files are present-but-wrong so content rules trip rather than passing
    vacuously. PY-003 cannot fail while the package dir exists, so the sweep test
    exempts it. Language no-ops (PROTO-008 for Python) and network-gated checks
    (MCP-024) now report n/a — neither pass nor fail — so they need no exemption.
    """
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-python\n")  # no sections, no client setup

    # pyproject present but wrong on every axis the PY rules check.
    _write(
        root / "pyproject.toml",
        """
        [build-system]
        requires = ["setuptools"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "bad-python"
        version = "0.1.0"
        requires-python = ">=3.10,<3.13"
        dependencies = ["requests"]

        [dependency-groups]
        dev = ["mypy"]
    """,
    )

    pkg = root / "src" / "bad_python"
    # server.py: no ServerContext dataclass, no FastMCP(...), a non-conforming
    # tool, and a logged secret.
    _write(
        pkg / "server.py",
        """
        import mcp

        @mcp.tool
        def BadTool(x):
            print("starting")
            logger.info("auth %s", api_key)
    """,
    )
    # errors.py present but defines no *Error(Exception) and no error mapping.
    _write(pkg / "errors.py", "x = 1\n")
    # clients/ has a retry-using client with no __init__.py and an untimed httpx.
    _write(
        pkg / "clients" / "client.py",
        "def fetch(u):\n    retry()\n    httpx.AsyncClient(base_url=u)\n",
    )
    # secret CLI arg + network transport without auth/loopback guard.
    _write(
        pkg / "cli.py",
        """
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--api-key")
        mcp.run(transport="sse", host="0.0.0.0")
    """,
    )

    _write(root / "__pycache__" / "stale.pyc", "")  # committed build artifact
    _write(root / ".env", "TOKEN=sekret\n")  # secret-shaped tracked file
    # A workflow with an unpinned action (trips MCP-017) but no ci.yml.
    _write(
        root / ".github" / "workflows" / "extra.yml",
        "name: extra\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n",
    )
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
    _write(root / "CONTRIBUTING.md", "## How to contribute\n\n## Release\nTag and push.\n")
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

            "github.com/mark3labs/mcp-go/server"
        )

        func errToMCP(err error) error { return err }

        func main() {
            allowWrites := os.Getenv("GOOD_GO_ALLOW_WRITES")
            _ = allowWrites
            srv := server.NewServer("good-go", server.WithCapabilities())
            _ = srv
            _ = errToMCP
            slog.New(slog.NewJSONHandler(os.Stderr, nil))
            // failures return &mcp.CallToolResult{IsError: true}
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
        root / "internal" / "tools" / "fuzz_test.go",
        'package tools\nimport "testing"\nfunc FuzzGet(f *testing.F) { _ = f }\n',
    )

    _write(root / ".github" / "workflows" / "security.yml", "name: security\non: schedule\n")
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
              - run: govulncheck ./...
              - run: go test ./... -race -count=1 -covermode=atomic -coverprofile=cover.out
              - run: go-test-coverage --config .testcoverage.yml
    """,
    )
    _write(root / ".github" / "dependabot.yml", "version: 2\nupdates: []\n")
    _write(root / "docs" / "README.md", "# Docs\n")
    return root


def build_bad_go(root: Path) -> Path:
    """Create a Go repo that fails every applicable rule it can.

    The single internal source file violates the GO-* library rules and the
    language-agnostic PROTO rules at once. The Python-only PROTO rules
    (PROTO-003/004/015) and the network-gated MCP-024 now report n/a for Go —
    neither pass nor fail — so they need no exemption.
    """
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "README.md", "# bad-go\n")  # no sections, no client setup

    # No go.mod / go.sum / .golangci.yml / ci.yml: trips GO-002/003/004/005/007
    # and GO-012. internal/ exists (so the content rules can trip) but cmd/ does
    # not, so GO-001 still fails.
    _write(
        root / "internal" / "tools" / "bad.go",
        """
        package tools

        import (
            "flag"
            "fmt"
            "log"
            "net/http"
            "os"
        )

        func init() {
            a := 1
            b := 2
            c := 3
            d := 4
            _ = a + b + c + d
        }

        var key = flag.String("api-key", "", "secret token")
        var _ = WithTools("BadTool")

        func WithTools(name string) int { return 0 }

        func ClientGet(id string) (string, error) {
            apiKey := *key
            log.Printf("using %s", apiKey)
            fmt.Println("starting")
            _ = &http.Client{}
            _ = os.Getenv("MCP_TRANSPORT")
            go doStuff()
            if id == "" {
                panic("boom")
            }
            resp, err := http.Get(id)
            _ = resp
            return id, err
        }

        func doStuff() {}
    """,
    )

    _write(root / "stale.pyc", "")  # committed build artifact
    _write(root / ".env", "TOKEN=sekret\n")  # secret-shaped tracked file
    _write(
        root / ".github" / "workflows" / "extra.yml",
        "name: extra\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n",
    )
    return root
