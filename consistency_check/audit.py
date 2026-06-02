"""Audit driver: walks repos, runs applicable rules, collects findings."""

from __future__ import annotations

import importlib
import traceback
from typing import TYPE_CHECKING

from consistency_check.types import Finding, FindingStatus, Repo, Rule, Tier

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
    "consistency_check.rules.stage_meta",
)


def all_rules() -> tuple[Rule, ...]:
    """Load every rule from every registered rule module."""
    out: list[Rule] = []
    for mod_name in _RULE_MODULES:
        mod = importlib.import_module(mod_name)
        out.extend(mod.RULES)
    return tuple(out)


def audit_repo(repo: Repo) -> list[Finding]:
    """Run all applicable rules against ``repo`` and return findings, isolating crashes."""
    if not repo.path.exists():
        return [
            Finding(
                rule_id="REPO-MISSING",
                tier=Tier.MUST,
                status=FindingStatus.ERROR,
                evidence=f"path does not exist: {repo.path}",
            )
        ]

    findings: list[Finding] = []
    for rule in all_rules():
        if repo.language not in rule.applies_to:
            findings.append(Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.NA))
            continue
        try:
            evidence = rule.check(repo)
        except Exception as exc:  # noqa: BLE001 — isolation by design
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.ERROR,
                    evidence=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}",
                )
            )
            continue
        if evidence is None:
            findings.append(Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.PASS))
        else:
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.FAIL,
                    evidence=evidence,
                )
            )

    return findings


def audit_all(repos: Iterable[Repo]) -> dict[str, list[Finding]]:
    """Audit every repo in ``repos``; return mapping of repo name → findings."""
    return {repo.name: audit_repo(repo) for repo in repos}
