"""Meta-rules: stage declaration and stage drift (MAY-tier, never block exit 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.stage import declared_stage, drift_signal
from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo


def _check_stage_declared(repo: Repo) -> str | None:
    if declared_stage(repo) is None:
        return "README ## Status section declares no S0-S4 stage token (unstaged)"
    return None


def _check_stage_drift(repo: Repo) -> str | None:
    declared = declared_stage(repo)
    if declared is None:
        return None
    return drift_signal(repo, declared)


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-STAGE-DECL",
        tier=Tier.MAY,
        statement="README ## Status declares a maturity stage (S0-S4)",
        check=_check_stage_declared,
        min_stage=Stage.S0,
    ),
    Rule(
        id="MCP-STAGE-DRIFT",
        tier=Tier.MAY,
        statement="Declared stage matches the repo's cheap structural signals",
        check=_check_stage_drift,
        min_stage=Stage.S0,
    ),
)
