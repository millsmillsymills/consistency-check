"""Sweep enforcing the fixture contract: good_* passes, bad_* fails.

CLAUDE.md states the invariant that the ``good_*`` fixtures satisfy every
applicable rule and the ``bad_*`` fixtures violate every one. The good side is
asserted in full. The bad side cannot be total: a handful of rules pass in
isolation no matter the input, so they are exempted with the reason inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check.audit import all_rules
from consistency_check.types import Repo

from tests.fixtures.build import (
    build_bad_go,
    build_bad_python,
    build_good_go,
    build_good_python,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from consistency_check.types import Rule

_GOOD: dict[str, Callable[[Path], Path]] = {
    "python": build_good_python,
    "go": build_good_go,
}
_BAD: dict[str, Callable[[Path], Path]] = {
    "python": build_bad_python,
    "go": build_bad_go,
}

# Rules that pass on any input of that language, and so cannot be tripped by
# its bad fixture. Keyed by the language that cannot fail them:
#   python: PY-003   the src/<pkg>/ layout cannot be missing while the package
#                    dir exists, which the package-content rules require.
#   both:   MCP-024 is declared non-mechanical, so it never returns a verdict.
#           PROTO-022 cannot fire on the bad fixtures: each registers a tool (a
#           badly named one), and the guard only fires when *no* registration is
#           detectable. A fixture with no tools would make every other
#           tool-surface rule pass instead, which is the worse trade.
#           MCP-STAGE-DRIFT cannot fire on the bad fixtures: they are unstaged,
#           so the drift check returns None (it only compares against a declared
#           stage). MCP-STAGE-DECL still fails them. MCP-DEPLOY-DRIFT likewise:
#           they declare no archetype, so its check returns None while
#           MCP-DEPLOY-DECL still fails them.
_CANNOT_FAIL: dict[str, frozenset[str]] = {
    "python": frozenset({"MCP-024", "PROTO-022", "PY-003", "MCP-STAGE-DRIFT", "MCP-DEPLOY-DRIFT"}),
    "go": frozenset({"MCP-024", "PROTO-022", "MCP-STAGE-DRIFT", "MCP-DEPLOY-DRIFT"}),
}


def _repo(root: Path, language: str) -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _applicable(language: str) -> list[Rule]:
    return [rule for rule in all_rules() if language in rule.applies_to]


@pytest.mark.parametrize("language", ["python", "go"])
def test_good_fixture_passes_every_applicable_rule(tmp_path: Path, language: str) -> None:
    repo = _repo(_GOOD[language](tmp_path / f"good_{language}"), language)
    failed = {
        rule.id: result
        for rule in _applicable(language)
        if isinstance(result := rule.check(repo), str)
    }
    assert not failed, f"good_{language} should pass every rule but failed: {failed}"


@pytest.mark.parametrize("language", ["python", "go"])
def test_bad_fixture_fails_every_applicable_rule(tmp_path: Path, language: str) -> None:
    """Only ``None`` counts as a pass here.

    A ``NotApplicable`` is not a pass and must not be scored as one, or a rule
    that quietly stops evaluating reads as covered by this sweep — the exact
    regression the sentinel exists to prevent.
    """
    repo = _repo(_BAD[language](tmp_path / f"bad_{language}"), language)
    exempt = _CANNOT_FAIL[language]
    passed = [
        rule.id
        for rule in _applicable(language)
        if rule.id not in exempt and rule.check(repo) is None
    ]
    assert not passed, f"bad_{language} should fail every non-exempt rule but passed: {passed}"


@pytest.mark.parametrize("language", ["python", "go"])
def test_exempt_rules_really_cannot_fail(tmp_path: Path, language: str) -> None:
    repo = _repo(_BAD[language](tmp_path / f"bad_{language}"), language)
    applicable = {rule.id: rule for rule in _applicable(language)}
    exempt = _CANNOT_FAIL[language]

    stale = sorted(exempt - applicable.keys())
    assert not stale, f"_CANNOT_FAIL[{language}] names rules that do not apply: {stale}"

    tripped = {
        rule_id: result
        for rule_id in sorted(exempt)
        if isinstance(result := applicable[rule_id].check(repo), str)
    }
    assert not tripped, (
        f"_CANNOT_FAIL[{language}] over-exempts: these fail on bad_{language} "
        f"and belong in the sweep: {tripped}"
    )
