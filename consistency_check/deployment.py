"""Deployment-archetype parsing and drift signals.

Pure and side-effect-free: every function reads repo files and returns data.
Mirrors stage.py, which does the same for the maturity-stage axis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.stage import status_section_text
from consistency_check.types import Archetype

if TYPE_CHECKING:
    from consistency_check.types import Repo

_DEPLOYMENT_TOKEN = re.compile(r"(?i)\bdeployment:\s*(remote-hostable|site-local|host-local)\b")


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
