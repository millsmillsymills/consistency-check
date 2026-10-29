"""Version-bound Skylos output contracts; incomplete analysis never means clean."""

from __future__ import annotations

import json
from typing import Any

ADAPTER_VERSION = 1
_DEAD_FIELDS = (
    "unused_functions",
    "unused_imports",
    "unused_classes",
    "unused_variables",
    "unused_parameters",
    "unused_files",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _objects(value: Any, name: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), f"missing/non-list {name}")
    _require(all(isinstance(item, dict) for item in value), f"non-object {name} entry")
    return value


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"missing/non-object {name}")
    return value


def validate_output(raw: bytes, code: int, mode: str, language: str) -> dict[str, Any]:
    """Return an observation, never an assessment/adoption verdict."""
    payload = json.loads(raw)
    _require(isinstance(payload, dict), "output must be an object")
    if mode == "verify":
        return _verify(payload, code, language)
    return _static(payload, code, mode, language)


def _verify(payload: dict[str, Any], code: int, language: str) -> dict[str, Any]:
    _require(
        type(payload.get("schema_version")) is int and payload["schema_version"] == 2,
        "unsupported verify schema",
    )
    status = payload["status"]
    _require(status in {"pass", "fail", "incomplete"}, "invalid verify status")
    _require(code == {"pass": 0, "fail": 1, "incomplete": 2}[status], "exit/status contradiction")
    findings = _objects(payload.get("findings"), "findings")
    coverage = _object(payload.get("coverage"), "coverage")
    _require(
        isinstance(coverage, dict)
        and type(coverage.get("schema_version")) is int
        and coverage["schema_version"] == 1,
        "missing/unsupported coverage schema",
    )
    for field in ("detected_languages", "completed_checks", "missing_checks", "skipped_checks"):
        _require(isinstance(coverage.get(field), list), f"missing/non-list coverage {field}")
    _require(language in coverage.get("detected_languages", []), "requested language unmeasured")
    support = _objects(coverage.get("language_support"), "language_support")
    expected_checks = _objects(coverage.get("expected_checks"), "expected_checks")
    checks = _objects(coverage.get("checks"), "checks")
    required = {item["id"] for item in expected_checks if language in item.get("languages", [])}
    by_id = {item["id"]: item for item in checks}
    language_support = [item for item in support if item.get("language") == language]
    supported = bool(language_support) and all(
        item.get("status") == "supported" for item in language_support
    )
    complete = (
        supported
        and status != "incomplete"
        and coverage.get("state") == "complete"
        and bool(coverage.get("completed_checks"))
        and not coverage.get("missing_checks")
        and not coverage.get("skipped_checks")
        and bool(required)
        and required.issubset(coverage["completed_checks"])
        and all(
            by_id.get(name, {}).get("status") == "completed"
            and by_id[name].get("outcome") in {"pass", "fail"}
            and by_id[name].get("skipped_references", 0) == 0
            for name in required
        )
    )
    return {
        "state": "complete" if complete else "incomplete",
        "scanner_verdict": status,
        "findings": findings,
        "coverage": coverage,
        "upstream_schema": 2,
    }


def _static(payload: dict[str, Any], code: int, mode: str, language: str) -> dict[str, Any]:
    _require("schema_version" not in payload, "unknown static schema; review adapter before reuse")
    _require(mode in {"dead-code", "security", "quality"}, "unknown static mode")
    _require(code in {0, 1, 2}, "scanner execution failed")
    summary = _object(payload.get("analysis_summary"), "analysis summary")
    languages = _object(summary.get("languages"), "language counts")
    count = languages.get({"python": "Python", "go": "Go"}[language])
    _require(type(count) is int and count > 0, "requested language unmeasured")
    _require(
        type(summary.get("total_files")) is int and summary["total_files"] >= count,
        "missing/invalid source file count",
    )
    category = {"dead-code": "dead_code", "security": "security", "quality": "quality"}[mode]
    _require(
        isinstance(summary.get("grade_categories"), list)
        and category in summary["grade_categories"],
        "requested check did not run",
    )
    errors = _objects(payload.get("analysis_errors"), "analysis_errors")
    suppressed = _objects(payload.get("suppressed"), "suppressed")
    fields = (
        _DEAD_FIELDS if mode == "dead-code" else ("danger" if mode == "security" else "quality",)
    )
    findings = [item for field in fields for item in _objects(payload.get(field), field)]
    complete = (
        code != 2
        and not errors
        and summary.get("analysis_error_count") == 0
        and not summary.get("incomplete_languages")
        and summary.get("grade_unavailable_reason") != "analysis_incomplete"
    )
    grep = summary.get("grep_verify", {})
    _require(isinstance(grep, dict), "invalid grep coverage")
    complete = complete and grep.get("complete") is not False
    if language == "go":
        complete = complete and _go_complete(summary, category)
    return {
        "state": "complete" if complete else "incomplete",
        "scanner_verdict": "findings" if findings else "no_findings",
        "findings": findings,
        "suppressed": suppressed,
        "coverage": summary,
        "upstream_schema": "unversioned-skylos-5.1.5",
    }


def _go_complete(summary: dict[str, Any], category: str) -> bool:
    engines = summary.get("language_engines", {})
    _require(isinstance(engines, dict), "missing Go engine coverage")
    engine = engines.get("go", {})
    _require(isinstance(engine, dict), "invalid Go engine coverage")
    return (
        engine.get("status") == "available"
        and category in engine.get("completed_checks", [])
        and category not in engine.get("skipped_checks", [])
    )
