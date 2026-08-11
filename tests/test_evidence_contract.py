"""The evidence contract every rule is held to.

Evidence is interpolated into a GitHub issue body that is filed against a public
repository. The renderer caps its length, but a cap is the wrong instrument for
the property that matters: 500 characters of a private repo's source is still a
publishable leak, and truncation keeps the front of it. The property the rules
actually have is that evidence names a thing — a rule subject, a filename, a
marker — and stays short. That is asserted here, against the fixtures that make
every applicable rule fail, so a matcher that starts capturing a source span is
caught where it is introduced rather than quietly shortened at render time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from consistency_check import audit as audit_mod
from consistency_check.audit import all_rules, audit_repo
from consistency_check.report import render_umbrella
from consistency_check.types import FindingStatus, Repo, Rule, Tier

from tests.fixtures.build import build_bad_go, build_bad_python

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_BAD: dict[str, Callable[[Path], Path]] = {"python": build_bad_python, "go": build_bad_go}

# Comfortably above the longest evidence any rule produces today and far below
# the renderer's 500-character cap, so this trips before truncation ever does.
_MAX_EVIDENCE = 200


@pytest.mark.parametrize("language", ["python", "go"])
def test_every_failing_rule_reports_short_single_line_evidence(
    tmp_path: Path, language: str
) -> None:
    repo = Repo(
        name=f"bad_{language}",
        path=_BAD[language](tmp_path / f"bad_{language}"),
        language=language,
        github_slug="x/y",
    )
    offenders = {
        rule.id: evidence
        for rule in all_rules()
        if language in rule.applies_to
        and (evidence := rule.check(repo)) is not None
        and (len(evidence) > _MAX_EVIDENCE or "\n" in evidence)
    }
    assert not offenders, (
        f"evidence must be a short single-line name, not a span of the audited "
        f"repo's source, which the filer would publish: {offenders}"
    )


def test_a_missing_repo_reports_no_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    absent = tmp_path / "not-cloned-here"
    repo = Repo(name="ghost", path=absent, language="python", github_slug="x/y")

    findings = audit_repo(repo)

    assert [f.rule_id for f in findings] == ["REPO-MISSING"]
    assert str(absent) not in findings[0].evidence
    assert str(absent) in capsys.readouterr().err


def test_a_raising_rule_reports_only_its_exception_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = build_bad_python(tmp_path / "bad_python")
    missing = root / "definitely" / "absent.toml"

    def boom(_repo: Repo) -> str | None:
        return missing.read_text(encoding="utf-8")

    monkeypatch.setattr(
        audit_mod,
        "all_rules",
        lambda: [Rule(id="X-999", tier=Tier.MUST, statement="boom", check=boom)],
    )
    repo = Repo(name="bad_python", path=root, language="python", github_slug="x/y")
    errors = [f for f in audit_repo(repo) if f.status == FindingStatus.ERROR]

    assert [f.evidence for f in errors] == ["FileNotFoundError"]
    # The detail a human needs is not lost, it is only kept off the filed body.
    assert str(missing) in capsys.readouterr().err
    assert str(missing) not in render_umbrella("bad_python", errors)
