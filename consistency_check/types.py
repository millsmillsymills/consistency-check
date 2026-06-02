"""Core dataclasses for the consistency-check audit tool."""  # noqa: A005

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class Tier(StrEnum):
    """RFC 2119 compliance tier."""

    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"


class FindingStatus(StrEnum):
    """Outcome of running a rule check against a repo."""

    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    NA = "n/a"
    ERROR = "error"


class Stage(StrEnum):
    """MCP server maturity stage. Completeness axis, orthogonal to Tier."""

    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


@dataclass(frozen=True, slots=True)
class Repo:
    """A target repository to be audited."""

    name: str
    path: Path
    language: str
    github_slug: str


@dataclass(frozen=True, slots=True)
class Finding:
    """A single rule outcome for one repo."""

    rule_id: str
    tier: Tier
    status: FindingStatus
    evidence: str = ""
    min_stage: Stage = Stage.S3


@dataclass(frozen=True, slots=True)
class Rule:
    """A single auditable standard.

    The check function returns evidence on failure or None on pass.
    """

    id: str
    tier: Tier
    statement: str
    check: Callable[[Repo], str | None]
    applies_to: frozenset[str] = field(default_factory=lambda: frozenset({"python", "go"}))
    min_stage: Stage = Stage.S3
