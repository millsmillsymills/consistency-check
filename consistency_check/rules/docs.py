"""Rules: documentation (MCP-003, 004, 007, 008, 009, 010, 027)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from consistency_check._git import tracked_files
from consistency_check.types import Rule, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

_README_GROUPS = (
    {"status"},
    {"quick start", "install"},
    {"configuration", "environment variables"},
    {"development"},
    {"license"},
)
_CLIENT_NAMES = ("Claude Desktop", "Cursor", "Continue.dev", "Claude Code")
_STANDARDS_LINK = "consistency-check/docs/standards"

_PROSE_ROOT_FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md")
_BANNED_PHRASES = (
    Path.home()
    / "Desktop/Projects/claude-defaults-private/skills/writing-voice-review/banned-phrases.txt"
)
# The pattern file is written for ripgrep's PCRE2 engine, which accepts POSIX
# bracket expressions; Python's ``re`` reads ``[[:space:]]`` as a literal class.
_POSIX_CLASSES = {
    "alnum": r"a-zA-Z0-9",
    "alpha": r"a-zA-Z",
    "blank": r" \t",
    "digit": r"0-9",
    "lower": r"a-z",
    "punct": r"!-/:-@\[-`{-~",
    "space": r"\s",
    "upper": r"A-Z",
    "xdigit": r"0-9a-fA-F",
}
_MAX_PROSE_HITS = 5


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _h2s(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"(?m)^##\s+(.+?)\s*$", text)}


def _check_changelog(repo: Repo) -> str | None:
    cl = repo.path / "CHANGELOG.md"
    if not cl.is_file():
        return "CHANGELOG.md missing"
    text = _read(cl)
    if not re.search(r"(?m)^##\s+\[(Unreleased|\d+\.\d+\.\d+)\]", text):
        return "CHANGELOG.md does not use Keep-a-Changelog headings"
    return None


def _check_contributing(repo: Repo) -> str | None:
    return None if (repo.path / "CONTRIBUTING.md").is_file() else "CONTRIBUTING.md missing"


def _check_readme_sections(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md").lower()
    if not text:
        return "README.md missing"
    found = _h2s(text)
    missing_groups = [g for g in _README_GROUPS if not (g & found)]
    if missing_groups:
        return f"README missing required sections: {[sorted(g) for g in missing_groups]}"
    return None


def _check_readme_clients(repo: Repo) -> str | None:
    text = _read(repo.path / "README.md")
    if any(name in text for name in _CLIENT_NAMES):
        return None
    return (
        "README does not declare any MCP client setup"
        " (Claude Desktop, Cursor, Continue.dev, Claude Code)"
    )


def _check_claude_md_link(repo: Repo) -> str | None:
    text = _read(repo.path / "CLAUDE.md")
    if _STANDARDS_LINK in text:
        return None
    return f"CLAUDE.md does not reference {_STANDARDS_LINK}"


def _check_docs_dir(repo: Repo) -> str | None:
    docs = repo.path / "docs"
    if not docs.is_dir():
        return "docs/ directory missing"
    if not any(docs.rglob("*.md")):
        return "docs/ contains no markdown"
    return None


def _banned_phrase_patterns() -> list[tuple[str, re.Pattern[str]]]:
    try:
        raw = _BANNED_PHRASES.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read the writing-voice banned-phrase list at {_BANNED_PHRASES}: {exc}"
        raise RuntimeError(msg) from exc
    patterns = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        translated = line
        for name, expansion in _POSIX_CLASSES.items():
            translated = translated.replace(f"[:{name}:]", expansion)
        patterns.append((line, re.compile(translated, re.IGNORECASE)))
    return patterns


def _prose_surfaces(repo: Repo) -> list[str]:
    found = [name for name in _PROSE_ROOT_FILES if (repo.path / name).is_file()]
    docs = repo.path / "docs"
    if docs.is_dir():
        found.extend(p.relative_to(repo.path).as_posix() for p in docs.rglob("*.md"))
    tracked = tracked_files(repo.path)
    return sorted(rel for rel in found if not tracked or rel in tracked)


def _check_writing_voice(repo: Repo) -> str | None:
    patterns = _banned_phrase_patterns()
    hits: list[str] = []
    for rel in _prose_surfaces(repo):
        text = _read(repo.path / rel)
        for lineno, line in enumerate(text.splitlines(), start=1):
            hits.extend(
                f"{rel}:{lineno} {match.group(0)!r} (banned: {raw})"
                for raw, pattern in patterns
                if (match := pattern.search(line))
            )
    if not hits:
        return None
    tail = f" and {len(hits) - _MAX_PROSE_HITS} more" if len(hits) > _MAX_PROSE_HITS else ""
    return f"banned writing-voice phrases: {'; '.join(hits[:_MAX_PROSE_HITS])}{tail}"


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-003",
        tier=Tier.SHOULD,
        statement="CHANGELOG.md present, Keep-a-Changelog format",
        check=_check_changelog,
    ),
    Rule(
        id="MCP-004",
        tier=Tier.SHOULD,
        statement="CONTRIBUTING.md present",
        check=_check_contributing,
    ),
    Rule(
        id="MCP-007",
        tier=Tier.MUST,
        statement="README has required sections",
        check=_check_readme_sections,
    ),
    Rule(
        id="MCP-008",
        tier=Tier.SHOULD,
        statement="README declares MCP client setup",
        check=_check_readme_clients,
    ),
    Rule(
        id="MCP-009",
        tier=Tier.MUST,
        statement="CLAUDE.md references canonical standards",
        check=_check_claude_md_link,
    ),
    Rule(
        id="MCP-010",
        tier=Tier.SHOULD,
        statement="docs/ exists with markdown content",
        check=_check_docs_dir,
    ),
    Rule(
        id="MCP-027",
        tier=Tier.MUST,
        statement="Prose surfaces are free of writing-voice banned phrases",
        check=_check_writing_voice,
    ),
)
