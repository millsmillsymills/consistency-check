"""Pinned output contracts reject incomplete, unsupported, and suppressed-as-clean claims."""

from __future__ import annotations

import copy
import json

import pytest
from assessments.skylos.results import validate_output


def _static(language="python", mode="dead-code"):
    category = {"dead-code": "dead_code", "security": "security", "quality": "quality"}[mode]
    return {
        "unused_functions": [],
        "unused_imports": [],
        "unused_classes": [],
        "unused_variables": [],
        "unused_parameters": [],
        "unused_files": [],
        "danger": [],
        "quality": [],
        "suppressed": [],
        "analysis_errors": [],
        "analysis_summary": {
            "languages": {"Python" if language == "python" else "Go": 1},
            "total_files": 1,
            "analysis_error_count": 0,
            "grade_categories": [category],
            "language_engines": {
                "go": {"status": "available", "completed_checks": [category], "skipped_checks": []}
            },
        },
    }


@pytest.mark.parametrize("language", ["python", "go"])
@pytest.mark.parametrize("mode", ["dead-code", "security", "quality"])
def test_complete_static_families_have_separate_observations(language, mode) -> None:
    result = validate_output(json.dumps(_static(language, mode)).encode(), 0, mode, language)
    assert result["state"] == "complete"
    assert result["findings"] == []
    assert result["upstream_schema"] == "unversioned-skylos-5.1.5"


@pytest.mark.parametrize(
    "field", ["analysis_errors", "analysis_summary", "suppressed", "unused_functions"]
)
def test_truncated_static_objects_cannot_be_complete(field) -> None:
    payload = _static()
    del payload[field]
    with pytest.raises((ValueError, TypeError)):
        validate_output(json.dumps(payload).encode(), 0, "dead-code", "python")


def test_missing_native_engine_is_unmeasured_even_with_no_findings() -> None:
    payload = _static("go")
    payload["analysis_summary"]["language_engines"]["go"] = {
        "status": "partial",
        "completed_checks": ["quality"],
        "skipped_checks": ["dead_code"],
    }
    result = validate_output(json.dumps(payload).encode(), 0, "dead-code", "go")
    assert result["state"] == "incomplete"


def test_suppressed_findings_remain_visible_in_an_observation() -> None:
    payload = _static()
    payload["suppressed"] = [{"rule_id": "example", "reason": "registered exception"}]
    result = validate_output(json.dumps(payload).encode(), 0, "dead-code", "python")
    assert result["suppressed"] == payload["suppressed"]
    malformed = copy.deepcopy(payload)
    malformed["suppressed"] = "silenced"
    with pytest.raises(ValueError, match="suppressed"):
        validate_output(json.dumps(malformed).encode(), 0, "dead-code", "python")


@pytest.mark.parametrize("diagnostic", ["analysis_errors", "incomplete_languages", "grep_verify"])
def test_static_coverage_gaps_cannot_be_clean(diagnostic) -> None:
    payload = _static()
    if diagnostic == "analysis_errors":
        payload[diagnostic] = [{"kind": "parse_failed"}]
    else:
        payload["analysis_summary"][diagnostic] = (
            ["Python"] if diagnostic == "incomplete_languages" else {"complete": False}
        )
    assert (
        validate_output(json.dumps(payload).encode(), 0, "dead-code", "python")["state"]
        == "incomplete"
    )


def test_a_new_upstream_schema_requires_adapter_review() -> None:
    payload = _static()
    payload["schema_version"] = 1
    with pytest.raises(ValueError, match="schema"):
        validate_output(json.dumps(payload).encode(), 0, "dead-code", "python")
