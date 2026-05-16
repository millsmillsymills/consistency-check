# Python MCP Standards (`PY-*`)

Applies to MCP servers written in Python. Built on top of `mcp.md`.

## Project metadata

### PY-001 — Build backend is `hatchling` (libraries) or `uv_build` (apps) [MUST]

**Rationale.** Both are well-supported. PEP 517 backends without active maintenance are not.

**Mechanical check.** `pyproject.toml::build-system.build-backend` is `"hatchling.build"` or `"uv_build"`.

### PY-002 — `requires-python >= "3.13"` [SHOULD]

**Rationale.** Project standard pins to 3.13. Older minors raise per-project justification.

**Mechanical check.** `pyproject.toml::project.requires-python` parses to a specifier permitting 3.13.

### PY-003 — Project layout is `src/<package>/` [MUST]

**Rationale.** Avoids accidental imports from working directory.

**Mechanical check.** `src/<package>/__init__.py` exists where `<package>` matches `pyproject.toml::project.name` with hyphens replaced by underscores.

### PY-004 — Required modules: `server.py`, `config.py`, `errors.py`, `__main__.py` [MUST]

**Mechanical check.** All four files exist under `src/<package>/`.

### PY-005 — Subpackages `clients/` and `tools/` [SHOULD]

**Rationale.** Separates protocol surface from API client logic.

**Mechanical check.** Both `src/<package>/clients/__init__.py` and `src/<package>/tools/__init__.py` exist.

### PY-006 — `py.typed` marker present [MUST]

**Rationale.** Downstream type checkers respect package types only when this marker exists.

**Mechanical check.** `src/<package>/py.typed` exists (file may be empty).

## Tooling

### PY-007 — Ruff configured in `pyproject.toml` [MUST]

**Mechanical check.** `pyproject.toml::tool.ruff` exists with `target-version` and `line-length` set.

### PY-008 — Type checker is `ty` (not `mypy`, not `pyright`) [MUST]

**Rationale.** Project standard. ty is faster and stricter.

**Mechanical check.** Dev deps include `ty`. Dev deps do NOT include `mypy` or `pyright`.

### PY-009 — Pre-commit hooks via `prek` [SHOULD]

**Mechanical check.** `.pre-commit-config.yaml` exists; `CONTRIBUTING.md` or README references `prek install` or `prek run`.

### PY-010 — `uv.lock` committed [MUST]

**Mechanical check.** `uv.lock` exists at repo root.

## Tests

### PY-011 — pytest + pytest-asyncio in dev deps [MUST]

**Mechanical check.** Dev deps include both packages.

### PY-012 — `tests/conftest.py` present [SHOULD]

**Mechanical check.** File exists; contains at least one fixture (def `*_fixture` or `@pytest.fixture`).

### PY-013 — `tests/property/` with hypothesis [SHOULD]

**Mechanical check.** Directory exists with at least one test using `from hypothesis import`.

### PY-014 — `tests/integration/` exists [SHOULD]

**Mechanical check.** Directory exists. Tests inside skip cleanly when their required env vars are absent.

## Idioms

### PY-015 — `from __future__ import annotations` in every module [MUST]

**Rationale.** Forward-compatible with PEP 563 and avoids runtime cost of evaluating annotations.

**Mechanical check.** Every `*.py` file under `src/` (excluding `__init__.py` files smaller than 200 bytes) contains a top-level `from __future__ import annotations`, detected by AST parse so module docstring length does not affect the check.

### PY-016 — FastMCP 3.x as the MCP framework [MUST]

**Mechanical check.** Direct dependency `fastmcp>=3.0,<4`.

### PY-017 — `httpx` for HTTP (no `requests`) [MUST]

**Mechanical check.** Direct deps include `httpx`. Direct deps do NOT include `requests`.

### PY-018 — `tenacity` for retries [SHOULD]

**Mechanical check.** Direct deps include `tenacity` if any client module uses retry logic.

### PY-019 — Typed lifespan context [MUST]

**Rationale.** Consistent, typed context shape across the suite. Either a named container or an explicit dict annotation makes the lifespan contract reviewable.

**Mechanical check.** `src/<package>/server.py` satisfies one of:

- defines a `@dataclass`-decorated class named `ServerContext`, **or**
- defines a lifespan with an explicit `AsyncIterator[dict[str, Any]]` yield annotation (required when composing with FastMCP's `{**left, **right}` lifespan merger, which `TypeError`s on a dataclass).

### PY-020 — Custom error hierarchy in `errors.py` [SHOULD]

**Mechanical check.** `src/<package>/errors.py` defines at least one class subclassing `Exception` with name ending in `Error`.
