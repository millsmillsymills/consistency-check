"""Deployment-archetype parsing and drift signals.

Pure and side-effect-free: every function reads repo files and returns data.
Mirrors stage.py, which does the same for the maturity-stage axis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.sources import combined_source_text
from consistency_check.stage import status_section_text
from consistency_check.types import Archetype

if TYPE_CHECKING:
    from consistency_check.types import Repo

_DEPLOYMENT_TOKEN = re.compile(r"(?i)\bdeployment:\s*(remote-hostable|site-local|host-local)\b")

_SERIAL_DEP = re.compile(r"(?i)serial|usb|hid")
_INTERACTIVE = re.compile(r"getpass|\binput\(")
_DEFAULT_PUBLIC_URL = re.compile(r"(?i)url\w*\"?\s*(?::\s*[\w\[\], .]+)?[:=]+\s*f?[\"']https://")
_SITE_MARKER = re.compile(r"(?i)_HOST\b|\bcontroller\b|\bappliance\b|\blan\b")


def declared_archetype(repo: Repo) -> Archetype | None:
    """Read the declared deployment archetype from the README ``## Status`` section.

    Returns the parsed Archetype, or None when the README is missing, has no
    ``## Status`` section, or that section carries no Deployment token.
    """
    section = status_section_text(repo)
    if section is None:
        return None
    token = _DEPLOYMENT_TOKEN.search(section)
    if token is None:
        return None
    return Archetype(token.group(1).lower())


def _manifest_text(repo: Repo) -> str:
    chunks: list[str] = []
    for name in ("pyproject.toml", "go.mod"):
        path = repo.path / name
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def deployment_drift_signal(repo: Repo, declared: Archetype) -> str | None:
    """Return a one-line drift description when cheap signals contradict ``declared``.

    Coarse static checks only; catches obvious contradictions, not a full re-audit.
    """
    if declared is Archetype.HOST_LOCAL and not _SERIAL_DEP.search(_manifest_text(repo)):
        return "declared host-local but no serial/USB dependency in the manifest"
    source = combined_source_text(repo)
    if declared is Archetype.REMOTE_HOSTABLE and _INTERACTIVE.search(source):
        return "declared remote-hostable but source prompts for interactive input at startup"
    # host-local only reaches this when a serial dep exists (the serial check
    # returns first); the regexes are deliberately loose substring heuristics.
    if declared in (Archetype.SITE_LOCAL, Archetype.HOST_LOCAL):
        readme = repo.path / "README.md"
        readme_text = (
            readme.read_text(encoding="utf-8", errors="replace") if readme.is_file() else ""
        )
        if (
            _DEFAULT_PUBLIC_URL.search(source)
            and not _INTERACTIVE.search(source)
            and not _SITE_MARKER.search(readme_text)
        ):
            return (
                f"declared {declared.value} but the backend looks like a public cloud API "
                "with token auth (looks remote-hostable)"
            )
    return None
