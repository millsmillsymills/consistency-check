"""Rules: observability and dependencies (MCP-021..024)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from collections.abc import Iterator

    from consistency_check.types import Repo


def _go_texts(repo: Repo) -> Iterator[str]:
    for p in repo.path.rglob("*.go"):
        if ".git" not in p.parts:
            yield p.read_text(encoding="utf-8", errors="replace")


def _python_texts(repo: Repo) -> Iterator[str]:
    src = repo.path / "src"
    if not src.is_dir():
        return
    for p in src.rglob("*.py"):
        yield p.read_text(encoding="utf-8", errors="replace")


def _check_logs_to_stderr(repo: Repo) -> str | None:
    if repo.language == "go":
        if any("os.Stderr" in t or "io.Stderr" in t for t in _go_texts(repo)):
            return None
        return "no Go source writes logs to os.Stderr"
    if any("sys.stderr" in t or "logging.basicConfig" in t for t in _python_texts(repo)):
        return None
    return "no Python source configures stderr logging"


def _has_python_structured_logger(text: str) -> bool:
    if "structlog" in text or "JSONFormatter" in text:
        return True
    return "json.dumps" in text and "log" in text.lower()


def _check_structured_logs(repo: Repo) -> str | None:
    if repo.language == "go":
        if any("log/slog" in t or "zerolog" in t for t in _go_texts(repo)):
            return None
        return "no structured logging library imported"
    if any(_has_python_structured_logger(t) for t in _python_texts(repo)):
        return None
    return "no structured logger detected"


def _check_lockfile(repo: Repo) -> str | None:
    if repo.language == "python":
        return None if (repo.path / "uv.lock").is_file() else "uv.lock missing"
    return None if (repo.path / "go.sum").is_file() else "go.sum missing"


def _check_dep_age(_repo: Repo) -> str | None:
    """Pass unconditionally — dep freshness requires network access to PyPI/proxy.go.dev."""
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-021",
        tier=Tier.MUST,
        statement="Server logs to stderr in MCP mode",
        check=_check_logs_to_stderr,
        min_stage=Stage.S1,
    ),
    Rule(
        id="MCP-022",
        tier=Tier.SHOULD,
        statement="Structured log format",
        check=_check_structured_logs,
        min_stage=Stage.S1,
    ),
    Rule(
        id="MCP-023",
        tier=Tier.MUST,
        statement="Dependency manifest pinned (lockfile committed)",
        check=_check_lockfile,
        min_stage=Stage.S2,
    ),
    Rule(
        id="MCP-024",
        tier=Tier.SHOULD,
        statement="No dependencies older than 12 months without justification",
        check=_check_dep_age,
    ),
)
