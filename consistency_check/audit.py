"""Audit driver: walks repos, runs applicable rules, collects findings."""

from __future__ import annotations

import importlib
import sys
import traceback
from functools import partial
from typing import TYPE_CHECKING

from consistency_check.deployment import declared_archetype
from consistency_check.stage import declared_stage, stage_rank
from consistency_check.types import (
    Archetype,
    Finding,
    FindingStatus,
    NotApplicable,
    Repo,
    Rule,
    Stage,
    Tier,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_RULE_MODULES = (
    "consistency_check.rules.structure",
    "consistency_check.rules.docs",
    "consistency_check.rules.tests",
    "consistency_check.rules.ci",
    "consistency_check.rules.security",
    "consistency_check.rules.deps",
    "consistency_check.rules.mcp_protocol",
    "consistency_check.rules.python",
    "consistency_check.rules.go",
    "consistency_check.rules.deployment",
    "consistency_check.rules.stage_meta",
)


def all_rules() -> tuple[Rule, ...]:
    """Load every rule from every registered rule module."""
    out: list[Rule] = []
    for mod_name in _RULE_MODULES:
        mod = importlib.import_module(mod_name)
        out.extend(mod.RULES)
    return tuple(out)


def _skip_finding(
    rule: Rule, repo: Repo, declared: Stage | None, declared_arch: Archetype | None
) -> Finding | None:
    """Return the n/a Finding for a rule that should not run, or None to run it."""
    na = partial(Finding, rule_id=rule.id, tier=rule.tier, status=FindingStatus.NA)
    if repo.language not in rule.applies_to:
        return na(min_stage=rule.min_stage, applicable=False)
    if declared is not None and stage_rank(rule.min_stage) > stage_rank(declared):
        return na(
            evidence=f"min_stage {rule.min_stage.value} above declared {declared.value}",
            min_stage=rule.min_stage,
        )
    if rule.applies_to_archetype is None:
        return None
    if declared_arch is None:
        return na(evidence="no Deployment archetype declared", min_stage=rule.min_stage)
    if declared_arch not in rule.applies_to_archetype:
        return na(evidence=f"not applicable to {declared_arch.value}", min_stage=rule.min_stage)
    return None


def audit_repo(repo: Repo) -> list[Finding]:
    """Run all applicable rules against ``repo`` and return findings, isolating crashes."""
    if not repo.path.exists():
        print(f"[{repo.name}] path does not exist: {repo.path}", file=sys.stderr)  # noqa: T201
        return [
            Finding(
                rule_id="REPO-MISSING",
                tier=Tier.MUST,
                status=FindingStatus.ERROR,
                evidence="repo path does not exist",
            )
        ]

    declared = declared_stage(repo)
    declared_arch = declared_archetype(repo)
    findings: list[Finding] = []
    for rule in all_rules():
        skipped = _skip_finding(rule, repo, declared, declared_arch)
        if skipped is not None:
            findings.append(skipped)
            continue
        try:
            evidence = rule.check(repo)
        except Exception as exc:  # noqa: BLE001 — isolation by design
            # Evidence is the exception type and nothing else, because the
            # renderer feeds it to a public issue body. An exception's message
            # is routinely the absolute path it failed to open, which would
            # publish the auditing machine's username and directory layout. The
            # detail a human needs goes to stderr, which is never filed.
            print(  # noqa: T201
                f"[{repo.name}] {rule.id} raised:\n{traceback.format_exc(limit=2)}",
                file=sys.stderr,
            )
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.ERROR,
                    evidence=type(exc).__name__,
                    min_stage=rule.min_stage,
                )
            )
            continue
        if isinstance(evidence, NotApplicable):
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.NA,
                    evidence=evidence.reason,
                    min_stage=rule.min_stage,
                    unevaluated=True,
                    unmechanized=evidence.unmechanized,
                )
            )
            continue
        status = FindingStatus.PASS if evidence is None else FindingStatus.FAIL
        findings.append(
            Finding(
                rule_id=rule.id,
                tier=rule.tier,
                status=status,
                evidence="" if evidence is None else evidence,
                min_stage=rule.min_stage,
            )
        )

    return findings


def audit_all(repos: Iterable[Repo]) -> dict[str, list[Finding]]:
    """Audit every repo in ``repos``; return mapping of repo name → findings."""
    return {repo.name: audit_repo(repo) for repo in repos}
