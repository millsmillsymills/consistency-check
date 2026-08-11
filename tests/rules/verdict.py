"""Shared unwrapping for rule tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.types import NotApplicable

if TYPE_CHECKING:
    from consistency_check.types import Repo, Rule


def verdict(rule: Rule, repo: Repo) -> str | None:
    """The rule's evidence, or None on pass.

    A rule that reports n/a never evaluated the repo, so a test asking it for a
    verdict must not silently read that as a pass.
    """
    result = rule.check(repo)
    assert not isinstance(result, NotApplicable), f"{rule.id} reported n/a: {result.reason}"
    return result
