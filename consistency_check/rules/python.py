"""Rules: Python (PY-001..020)."""

from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING, Any

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

_REQUIRED_BACKENDS = {"hatchling.build", "uv_build"}
_REQUIRED_MODULES = ("server.py", "config.py", "errors.py", "__main__.py")
_PY_ONLY = frozenset({"python"})


def _read_pyproject(repo: Repo) -> dict[str, Any] | None:
    f = repo.path / "pyproject.toml"
    if not f.is_file():
        return None
    try:
        return tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None


def _package_dir(repo: Repo) -> Path | None:
    pkg_name = repo.path.name.replace("-", "_")
    candidate = repo.path / "src" / pkg_name
    return candidate if candidate.is_dir() else None


def _dev_deps(cfg: dict[str, Any]) -> list[str]:
    deps: list[str] = []
    deps.extend(cfg.get("dependency-groups", {}).get("dev", []))
    deps.extend(cfg.get("project", {}).get("optional-dependencies", {}).get("dev", []))
    return [
        d.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip()
        for d in deps
    ]


def _has_dep(cfg: dict[str, Any], name: str) -> bool:
    deps = cfg.get("project", {}).get("dependencies", [])
    return any(d.lower().startswith(name.lower()) for d in deps)


def _check_build_backend(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return "pyproject.toml missing or unparseable"
    backend = cfg.get("build-system", {}).get("build-backend")
    if backend in _REQUIRED_BACKENDS:
        return None
    return f"build-backend is {backend!r}; require one of {sorted(_REQUIRED_BACKENDS)}"


def _check_requires_python(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    spec = cfg.get("project", {}).get("requires-python", "")
    if "3.13" in spec or "3.14" in spec:
        return None
    return f"requires-python = {spec!r}; project standard is 3.13"


def _check_layout(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    return None if pkg else f"src/{repo.path.name.replace('-', '_')}/ missing"


def _check_required_modules(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return "package directory missing"
    missing = [m for m in _REQUIRED_MODULES if not (pkg / m).is_file()]
    return f"missing modules: {missing}" if missing else None


def _check_subpackages(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    missing = [s for s in ("clients", "tools") if not (pkg / s / "__init__.py").is_file()]
    return f"missing subpackages: {missing}" if missing else None


def _check_py_typed(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    return None if (pkg / "py.typed").is_file() else "py.typed marker missing"


def _check_ruff(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    return None if "ruff" in cfg.get("tool", {}) else "no [tool.ruff] config"


def _check_type_checker(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = _dev_deps(cfg)
    if "ty" not in deps:
        return "ty not in dev dependencies"
    if "mypy" in deps or "pyright" in deps:
        return "mypy/pyright in dev dependencies; project standard is ty"
    return None


def _check_pre_commit(repo: Repo) -> str | None:
    return (
        None
        if (repo.path / ".pre-commit-config.yaml").is_file()
        else ".pre-commit-config.yaml missing"
    )


def _check_uv_lock(repo: Repo) -> str | None:
    return None if (repo.path / "uv.lock").is_file() else "uv.lock missing"


def _check_pytest_deps(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = _dev_deps(cfg)
    missing = [d for d in ("pytest", "pytest-asyncio") if d not in deps]
    return f"missing dev deps: {missing}" if missing else None


def _check_conftest(repo: Repo) -> str | None:
    cf = repo.path / "tests" / "conftest.py"
    if not cf.is_file():
        return "tests/conftest.py missing"
    return (
        None
        if "@pytest.fixture" in cf.read_text(encoding="utf-8")
        else "tests/conftest.py has no fixtures"
    )


def _check_property_dir(repo: Repo) -> str | None:
    return (
        None if (repo.path / "tests" / "property").is_dir() else "tests/property/ missing"
    )


def _check_integration_dir(repo: Repo) -> str | None:
    return (
        None
        if (repo.path / "tests" / "integration").is_dir()
        else "tests/integration/ missing"
    )


def _check_future_annotations(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    bad: list[str] = []
    for p in pkg.rglob("*.py"):
        if p.name == "__init__.py" and p.stat().st_size < 200:
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:600]
        if "from __future__ import annotations" not in head:
            bad.append(p.relative_to(repo.path).as_posix())
    return (
        f"missing 'from __future__ import annotations' in: {bad[:5]}" if bad else None
    )


def _check_fastmcp(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    return None if _has_dep(cfg, "fastmcp") else "fastmcp not in dependencies"


def _check_httpx(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    deps = cfg.get("project", {}).get("dependencies", [])
    if any(d.lower().startswith("requests") for d in deps):
        return "requests is in dependencies; require httpx"
    return None if _has_dep(cfg, "httpx") else "httpx not in dependencies"


def _check_tenacity(repo: Repo) -> str | None:
    cfg = _read_pyproject(repo)
    if cfg is None:
        return None
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    clients_dir = pkg / "clients"
    if not clients_dir.is_dir():
        return None
    needs_retry = any(
        "retry" in p.read_text(encoding="utf-8", errors="replace").lower()
        for p in clients_dir.rglob("*.py")
    )
    if needs_retry and not _has_dep(cfg, "tenacity"):
        return "client uses retries but tenacity is not a dependency"
    return None


def _check_server_context(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    server = pkg / "server.py"
    if not server.is_file():
        return None
    text = server.read_text(encoding="utf-8")
    if re.search(r"@dataclass[^\n]*\nclass\s+ServerContext\b", text):
        return None
    return "server.py does not define @dataclass class ServerContext"


def _check_error_hierarchy(repo: Repo) -> str | None:
    pkg = _package_dir(repo)
    if pkg is None:
        return None
    err = pkg / "errors.py"
    if not err.is_file():
        return None
    text = err.read_text(encoding="utf-8")
    if re.search(r"class\s+\w+Error\(Exception\b", text):
        return None
    return "errors.py defines no *Error(Exception, ...) class"


RULES: tuple[Rule, ...] = (
    Rule(
        id="PY-001",
        tier=Tier.MUST,
        statement="Build backend is hatchling or uv_build",
        check=_check_build_backend,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-002",
        tier=Tier.SHOULD,
        statement="requires-python >= 3.13",
        check=_check_requires_python,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-003",
        tier=Tier.MUST,
        statement="Project layout src/<package>/",
        check=_check_layout,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-004",
        tier=Tier.MUST,
        statement="Required modules present",
        check=_check_required_modules,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-005",
        tier=Tier.SHOULD,
        statement="Subpackages clients/ and tools/",
        check=_check_subpackages,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-006",
        tier=Tier.MUST,
        statement="py.typed marker present",
        check=_check_py_typed,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-007",
        tier=Tier.MUST,
        statement="Ruff configured",
        check=_check_ruff,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-008",
        tier=Tier.MUST,
        statement="Type checker is ty",
        check=_check_type_checker,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-009",
        tier=Tier.SHOULD,
        statement="Pre-commit hooks via prek",
        check=_check_pre_commit,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-010",
        tier=Tier.MUST,
        statement="uv.lock committed",
        check=_check_uv_lock,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-011",
        tier=Tier.MUST,
        statement="pytest + pytest-asyncio in dev deps",
        check=_check_pytest_deps,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-012",
        tier=Tier.SHOULD,
        statement="tests/conftest.py with fixtures",
        check=_check_conftest,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-013",
        tier=Tier.SHOULD,
        statement="tests/property/ exists",
        check=_check_property_dir,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-014",
        tier=Tier.SHOULD,
        statement="tests/integration/ exists",
        check=_check_integration_dir,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-015",
        tier=Tier.MUST,
        statement="from __future__ import annotations everywhere",
        check=_check_future_annotations,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-016",
        tier=Tier.MUST,
        statement="FastMCP 3.x dependency",
        check=_check_fastmcp,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-017",
        tier=Tier.MUST,
        statement="httpx dependency, no requests",
        check=_check_httpx,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-018",
        tier=Tier.SHOULD,
        statement="tenacity for retries",
        check=_check_tenacity,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-019",
        tier=Tier.MUST,
        statement="ServerContext dataclass in server.py",
        check=_check_server_context,
        applies_to=_PY_ONLY,
    ),
    Rule(
        id="PY-020",
        tier=Tier.SHOULD,
        statement="Custom error hierarchy in errors.py",
        check=_check_error_hierarchy,
        applies_to=_PY_ONLY,
    ),
)
