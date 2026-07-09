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


@dataclass(frozen=True, slots=True)
class NotApplicable:
    """Sentinel a check returns when it cannot mechanically evaluate this repo.

    Distinct from ``None`` (pass) and an evidence ``str`` (fail): the driver
    records it as :attr:`FindingStatus.NA` so a check that never actually ran
    (network-gated, or not implemented for this language) is never silently
    scored as a pass. ``reason`` is surfaced as the finding's evidence.
    """

    reason: str = ""


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


@dataclass(frozen=True, slots=True)
class Rule:
    """A single auditable standard.

    The check function returns ``None`` on pass, evidence ``str`` on failure, or
    a :class:`NotApplicable` when the rule cannot be mechanically evaluated.
    """

    id: str
    tier: Tier
    statement: str
    check: Callable[[Repo], str | None | NotApplicable]
    applies_to: frozenset[str] = field(default_factory=lambda: frozenset({"python", "go"}))
