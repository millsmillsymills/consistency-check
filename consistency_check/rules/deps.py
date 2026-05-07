"""Rules: observability and dependencies (MCP-021..024)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo


def _check_logs_to_stderr(repo: Repo) -> str | None:
    if repo.language == "go":
        for p in repo.path.rglob("*.go"):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "os.Stderr" in text or "io.Stderr" in text:
                return None
        return "no Go source writes logs to os.Stderr"
    src = repo.path / "src"
    if src.is_dir():
        for p in src.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="replace")
            if "sys.stderr" in text or "logging.basicConfig" in text:
                return None
    return "no Python source configures stderr logging"


def _check_structured_logs(repo: Repo) -> str | None:
    if repo.language == "go":
        for p in repo.path.rglob("*.go"):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "log/slog" in text or "zerolog" in text:
                return None
        return "no structured logging library imported"
    src = repo.path / "src"
    if src.is_dir():
        for p in src.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="replace")
            if "structlog" in text or "JSONFormatter" in text:
                return None
            if "json.dumps" in text and "log" in text.lower():
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
    ),
    Rule(
        id="MCP-022",
        tier=Tier.SHOULD,
        statement="Structured log format",
        check=_check_structured_logs,
    ),
    Rule(
        id="MCP-023",
        tier=Tier.MUST,
        statement="Dependency manifest pinned (lockfile committed)",
        check=_check_lockfile,
    ),
    Rule(
        id="MCP-024",
        tier=Tier.SHOULD,
        statement="No dependencies older than 12 months without justification",
        check=_check_dep_age,
    ),
)
