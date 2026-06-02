"""Rules: CI / release (MCP-014, 015, 016, 017, 018, 025, 026)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from pathlib import Path

    from consistency_check.types import Repo

# Documents the desired SHA-pinned-with-comment pattern for reference.
_SHA_PINNED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@([a-f0-9]{40})\s*(#\s*v\d|$)")
_TAG_USED = re.compile(r"uses:\s*([a-z0-9_.\-]+/[a-z0-9_.\-]+)@(?!([a-f0-9]{40}\b))[^\s]+")


def _read_workflows(repo: Repo) -> list[Path]:
    wf_dir = repo.path / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return [p for p in wf_dir.iterdir() if p.suffix in {".yml", ".yaml"}]


def _check_ci_workflow(repo: Repo) -> str | None:
    ci = repo.path / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        return ".github/workflows/ci.yml missing"
    text = ci.read_text(encoding="utf-8", errors="replace")
    if "push" not in text or "pull_request" not in text:
        return "ci.yml does not trigger on both push and pull_request"
    return None


def _check_security_workflow(repo: Repo) -> str | None:
    wf = repo.path / ".github" / "workflows"
    if (wf / "codeql.yml").is_file() or (wf / "security.yml").is_file():
        return None
    return "no codeql.yml / security.yml workflow"


def _check_dependabot(repo: Repo) -> str | None:
    db = repo.path / ".github" / "dependabot.yml"
    if not db.is_file():
        return ".github/dependabot.yml missing"
    return None


def _check_actions_pinned(repo: Repo) -> str | None:
    offenders: list[str] = []
    for wf in _read_workflows(repo):
        text = wf.read_text(encoding="utf-8", errors="replace")
        offenders.extend(f"{wf.name}: {m.group(0).strip()}" for m in _TAG_USED.finditer(text))
    if offenders:
        return f"unpinned action references: {offenders[:5]}"
    return None


_COVERAGE_GATE = re.compile(r"(?i)cov-fail-under|fail_under|covermode|coverprofile")
_VULN_SCAN = re.compile(
    r"(?i)pip-audit|govulncheck|osv-scanner|\btrivy\b|\bgrype\b|safety check"
    r"|dependency-review|\bsnyk\b"
)


def _ci_corpus(repo: Repo) -> str:
    parts = [wf.read_text(encoding="utf-8", errors="replace") for wf in _read_workflows(repo)]
    pyproject = repo.path / "pyproject.toml"
    if pyproject.is_file():
        parts.append(pyproject.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _check_coverage_threshold(repo: Repo) -> str | None:
    if _COVERAGE_GATE.search(_ci_corpus(repo)):
        return None
    return "CI does not enforce a coverage threshold (cov-fail-under / -covermode)"


def _check_vuln_scan(repo: Repo) -> str | None:
    if _VULN_SCAN.search(_ci_corpus(repo)):
        return None
    return "CI runs no dependency vulnerability scan (pip-audit / govulncheck)"


def _check_release_workflow(repo: Repo) -> str | None:
    if (repo.path / ".github" / "workflows" / "release.yml").is_file():
        return None
    contributing = repo.path / "CONTRIBUTING.md"
    if (
        contributing.is_file()
        and "release" in contributing.read_text(encoding="utf-8", errors="replace").lower()
    ):
        return None
    return "no release.yml and no documented release process"


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-014",
        tier=Tier.MUST,
        statement="ci.yml triggers on push and pull_request",
        check=_check_ci_workflow,
    ),
    Rule(
        id="MCP-015",
        tier=Tier.SHOULD,
        statement="Security workflow present",
        check=_check_security_workflow,
    ),
    Rule(
        id="MCP-016",
        tier=Tier.SHOULD,
        statement="Dependabot configuration present",
        check=_check_dependabot,
    ),
    Rule(
        id="MCP-017",
        tier=Tier.MUST,
        statement="GitHub Actions pinned to SHA",
        check=_check_actions_pinned,
    ),
    Rule(
        id="MCP-018",
        tier=Tier.MAY,
        statement="Release workflow exists",
        check=_check_release_workflow,
    ),
    Rule(
        id="MCP-025",
        tier=Tier.SHOULD,
        statement="CI enforces a coverage threshold",
        check=_check_coverage_threshold,
    ),
    Rule(
        id="MCP-026",
        tier=Tier.MUST,
        statement="CI runs a dependency vulnerability scan",
        check=_check_vuln_scan,
    ),
)
