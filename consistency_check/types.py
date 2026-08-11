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


class Archetype(StrEnum):
    """Deployment archetype. Locality axis, orthogonal to Stage and Tier."""

    REMOTE_HOSTABLE = "remote-hostable"
    SITE_LOCAL = "site-local"
    HOST_LOCAL = "host-local"


@dataclass(frozen=True, slots=True)
class NotApplicable:
    """What a check returns when it cannot evaluate the repo at all.

    Distinct from ``None`` (pass) and an evidence ``str`` (fail). A check that
    is gated on something the audit does not have (network access, a tool it
    does not run) otherwise has to return ``None``, which the driver scores as
    a pass and the summary counts as compliance the repo never demonstrated.

    ``unmechanized`` separates the two reasons a check declines, because they
    call for opposite handling. The default, a check that could not run *this
    time*, is an audit malfunction: the repo may well be violating the rule and
    nobody looked, so it escalates the exit code. ``unmechanized=True`` means no
    checker was ever written for this case; re-running changes nothing, so it is
    reported but does not escalate.

    A rule that simply does not apply to a repo's *language* does not need this:
    ``Rule.applies_to`` already records that as a permanent n/a.
    """

    reason: str
    unmechanized: bool = False


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
    # False when the rule's language does not match the repo's, which is a
    # permanent n/a: no promotion can ever turn it into work for this repo.
    applicable: bool = True
    # True when the n/a came from a check declining, not from scope. A scope
    # n/a means the rule is not this repo's problem yet; this one means the
    # rule is its problem and went ungraded, which has to reach the reader.
    unevaluated: bool = False
    unmechanized: bool = False


@dataclass(frozen=True, slots=True)
class Rule:
    """A single auditable standard.

    The check returns ``None`` on pass, an evidence ``str`` on failure, or a
    :class:`NotApplicable` when it cannot evaluate the repo at all.
    """

    id: str
    tier: Tier
    statement: str
    check: Callable[[Repo], str | None | NotApplicable]
    applies_to: frozenset[str] = field(default_factory=lambda: frozenset({"python", "go"}))
    min_stage: Stage = Stage.S3
    applies_to_archetype: frozenset[Archetype] | None = None
