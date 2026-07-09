"""Sweep enforcing the fixture contract: good_* passes, bad_* fails.

CLAUDE.md states the invariant that the ``good_*`` fixtures satisfy every
applicable rule and the ``bad_*`` fixtures violate every one. The good side is
asserted in full (an ``n/a`` outcome counts as satisfied — the check simply did
not apply). The bad side cannot be total: a rule that reports ``n/a`` never
fails, and a couple of rules pass in isolation no matter the input, so those are
exempted with the reason inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.audit import all_rules
from consistency_check.types import NotApplicable, Repo

from tests.fixtures.build import (
    build_bad_go,
    build_bad_python,
    build_good_go,
    build_good_python,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_GOOD: dict[str, Callable[[Path], Path]] = {
    "python": build_good_python,
    "go": build_good_go,
}
_BAD: dict[str, Callable[[Path], Path]] = {
    "python": build_bad_python,
    "go": build_bad_go,
}

# Rules that pass on any input and so cannot be tripped by a bad fixture.
# Checks that do not apply (MCP-024 network-gated; PROTO-003/004/008/015 the
# other language) now report n/a rather than pass, so they need no exemption.
#   PY-003  the src/<pkg>/ layout cannot be missing while the package dir
#           exists, which the package-content rules require.
_CANNOT_FAIL: dict[str, frozenset[str]] = {
    "python": frozenset({"PY-003"}),
    "go": frozenset(),
}


def _is_failure(evidence: str | None | NotApplicable) -> bool:
    """A check fails only when it returns evidence (not None/pass, not n/a)."""
    return evidence is not None and not isinstance(evidence, NotApplicable)


def _repo(root: Path, language: str) -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _applicable(language: str) -> list:
    return [rule for rule in all_rules() if language in rule.applies_to]


@pytest.mark.parametrize("language", ["python", "go"])
def test_good_fixture_passes_every_applicable_rule(tmp_path: Path, language: str) -> None:
    repo = _repo(_GOOD[language](tmp_path / f"good_{language}"), language)
    failed = {
        rule.id: evidence
        for rule in _applicable(language)
        if _is_failure(evidence := rule.check(repo))
    }
    assert not failed, f"good_{language} should pass every rule but failed: {failed}"


@pytest.mark.parametrize("language", ["python", "go"])
def test_bad_fixture_fails_every_applicable_rule(tmp_path: Path, language: str) -> None:
    repo = _repo(_BAD[language](tmp_path / f"bad_{language}"), language)
    exempt = _CANNOT_FAIL[language]
    passed = [
        rule.id
        for rule in _applicable(language)
        if rule.id not in exempt and rule.check(repo) is None
    ]
    assert not passed, f"bad_{language} should fail every non-exempt rule but passed: {passed}"
