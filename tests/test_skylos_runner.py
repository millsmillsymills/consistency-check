"""Exercise real subprocess failures, coverage validation, and artifact-bound resume."""

from __future__ import annotations

import copy
import json
import sys
import time
import tomllib

import pytest
from assessments.skylos.corpus import load_corpus, materialize
from assessments.skylos.environment import file_hash
from assessments.skylos.runner import Runner, command


def _payload(status="pass"):
    return {
        "schema_version": 2,
        "status": status,
        "findings": [],
        "coverage": {
            "schema_version": 1,
            "state": "complete",
            "detected_languages": ["python"],
            "completed_checks": ["local"],
            "missing_checks": [],
            "skipped_checks": [],
            "language_support": [{"language": "python", "status": "supported"}],
            "expected_checks": [{"id": "local", "languages": ["python"]}],
            "checks": [
                {"id": "local", "status": "completed", "outcome": "pass", "skipped_references": 0}
            ],
        },
    }


def _setup(tmp_path, payload=None, code=0, *, prefix="", raw=None, timeout=2):
    case = next(case for case in load_corpus()["cases"] if case["mode"] == "verify")
    root = tmp_path / "input"
    materialize(case, root)
    counter = tmp_path / "counter"
    scanner = tmp_path / "scanner"
    stdout = raw if raw is not None else json.dumps(payload or _payload()).encode()
    scanner.write_text(
        f"#!{sys.executable}\nimport os, sys, time, subprocess\nfrom pathlib import Path\n"
        f"counter = Path({str(counter)!r})\n"
        "counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else '1')\n"
        + prefix
        + f"\nos.write(1, {stdout!r})\nos.write(2, b'diagnostic')\nsys.exit({code})\n"
    )
    scanner.chmod(0o755)
    engine = tmp_path / "engine"
    engine.write_bytes(b"pinned engine")
    identity = {"scanner_sha256": file_hash(scanner), "go_engine": {"sha256": file_hash(engine)}}
    return Runner(scanner, engine, identity, tmp_path / "evidence", timeout), case, root, counter


def test_complete_observation_resumes_without_rerunning_the_scanner(tmp_path) -> None:
    runner, case, root, counter = _setup(tmp_path)
    first = runner.run(case, root)
    second = runner.run(case, root)
    assert first["valid_measurement"]
    assert first["state"] == "complete"
    assert second["resumed"]
    assert counter.read_text() == "1"
    assert (runner.store / first["key"] / "complete.json").is_file()
    assert tomllib.loads((runner.store / "trusted-empty.toml").read_text()) == {
        "tool": {"skylos": {}}
    }


@pytest.mark.parametrize("kind", ["unrelated", "requested", "unknown"])
def test_verify_skips_only_zero_file_checks_outside_requested_language(tmp_path, kind) -> None:
    payload = _payload()
    identifier = "local" if kind == "requested" else "typescript"
    payload["coverage"]["skipped_checks"] = [
        {"id": identifier, "reasons": [{"code": "no_supported_files"}]}
    ]
    if kind != "requested":
        payload["coverage"]["checks"].append(
            {
                "id": identifier,
                "languages": [],
                "applicable_files": 0,
                "status": "skipped",
                "outcome": "pass",
            }
        )
    if kind == "unknown":
        payload["coverage"]["skipped_checks"][0]["reasons"][0]["code"] = "engine_missing"
    runner, case, root, _ = _setup(tmp_path, payload)
    record = runner.run(case, root)
    assert record["valid_measurement"] == (kind == "unrelated")


def test_complete_scan_with_findings_is_preserved_as_findings_not_a_clean_verdict(tmp_path) -> None:
    payload = _payload("fail")
    payload["findings"] = [{"rule_id": "EXAMPLE", "range": {"file": "main.py", "start_line": 1}}]
    runner, case, root, _ = _setup(tmp_path, payload, 1)
    record = runner.run(case, root)
    assert record["valid_measurement"]
    assert record["observation"]["scanner_verdict"] == "fail"
    assert record["observation"]["findings"] == payload["findings"]


@pytest.mark.parametrize(
    "kind", ["malformed", "unknown_schema", "incomplete", "unsupported", "missing_check", "failure"]
)
def test_failed_and_incomplete_units_keep_raw_output_and_never_resume(tmp_path, kind) -> None:
    payload = _payload()
    code, raw = 0, None
    if kind == "malformed":
        raw = b'{"schema_version":'
    elif kind == "unknown_schema":
        payload["schema_version"] = 99
    elif kind == "incomplete":
        payload["status"], payload["coverage"]["state"], code = "incomplete", "incomplete", 2
    elif kind == "unsupported":
        payload["coverage"]["language_support"][0]["status"] = "unsupported"
    elif kind == "missing_check":
        payload["coverage"]["checks"] = []
    else:
        code = 9
    runner, case, root, counter = _setup(tmp_path, payload, code, raw=raw)
    first = runner.run(case, root)
    second = runner.run(case, root)
    assert not first["valid_measurement"]
    assert not second["resumed"]
    assert counter.read_text() == "2"
    attempts = list((runner.store / first["key"]).iterdir())
    assert len(attempts) == 2
    assert all((attempt / "stderr.bin").read_bytes() == b"diagnostic" for attempt in attempts)
    if raw is not None:
        assert all((attempt / "stdout.bin").read_bytes() == raw for attempt in attempts)


def test_timeout_terminates_descendants_and_preserves_partial_output(tmp_path) -> None:
    prefix = (
        "os.write(1, b'partial')\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'])\n"
        "time.sleep(5)\n"
    )
    runner, case, root, _ = _setup(tmp_path, prefix=prefix, timeout=0.3)
    started = time.monotonic()
    record = runner.run(case, root)
    assert time.monotonic() - started < 3
    assert record["state"] == "timeout"
    assert not record["valid_measurement"]
    attempt = next((runner.store / record["key"]).iterdir())
    assert (attempt / "stdout.bin").read_bytes() == b"partial"


@pytest.mark.parametrize("filename", ["stdout.bin", "stderr.bin", "result.json", "complete.json"])
def test_corrupt_cached_output_is_not_reused(tmp_path, filename) -> None:
    runner, case, root, counter = _setup(tmp_path)
    first = runner.run(case, root)
    receipt = json.loads((runner.store / first["key"] / "complete.json").read_text())
    directory = runner.store / first["key"]
    target = (
        directory / filename
        if filename == "complete.json"
        else directory / receipt["attempt"] / filename
    )
    target.write_bytes(b"truncated")
    second = runner.run(case, root)
    assert not second["resumed"]
    assert second["resume_rejected"]
    assert counter.read_text() == "2"


def test_missing_engine_cannot_run_a_scanner(tmp_path) -> None:
    runner, case, root, counter = _setup(tmp_path)
    runner.engine.unlink()
    with pytest.raises(FileNotFoundError):
        runner.run(case, root)
    assert not counter.exists()


def test_distinct_samples_and_environment_identities_do_not_share_measurements(tmp_path) -> None:
    runner, case, root, counter = _setup(tmp_path)
    first = runner.run(case, root, sample=1)
    second = runner.run(case, root, sample=2)
    identity = copy.deepcopy(runner.identity)
    identity["configuration_revision"] = "new"
    changed = Runner(runner.scanner, runner.engine, identity, runner.store, runner.timeout)
    third = changed.run(case, root, sample=1)
    assert len({first["key"], second["key"], third["key"]}) == 3
    assert counter.read_text() == "3"


def test_missing_engine_or_changed_scanner_fails_preflight(tmp_path) -> None:
    runner, case, root, counter = _setup(tmp_path)
    runner.scanner.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        runner.run(case, root)
    assert not counter.exists()


def test_scanner_execution_failure_is_recorded(tmp_path) -> None:
    runner, case, root, _ = _setup(tmp_path)
    runner.scanner.chmod(0o600)
    record = runner.run(case, root)
    assert record["state"] == "error"
    assert not record["valid_measurement"]


def test_source_mutation_cannot_create_a_reusable_observation(tmp_path) -> None:
    prefix = "(Path(sys.argv[2]) / 'extra.py').write_text('pass')\n"
    runner, case, root, _ = _setup(tmp_path, prefix=prefix)
    record = runner.run(case, root)
    assert record["state"] == "input_changed"
    assert not record["valid_measurement"]


def test_destroyed_git_context_still_preserves_raw_scanner_evidence(tmp_path) -> None:
    prefix = "(Path(sys.argv[2]) / '.git' / 'HEAD').unlink()\n"
    runner, case, root, _ = _setup(tmp_path, prefix=prefix)
    record = runner.run(case, root)
    assert record["state"] == "input_changed"
    assert not record["valid_measurement"]
    directory = runner.store / record["key"]
    assert not (directory / "complete.json").exists()
    attempt = next(directory.iterdir())
    assert (attempt / "stdout.bin").read_bytes() == json.dumps(_payload()).encode()
    assert (attempt / "stderr.bin").read_bytes() == b"diagnostic"


def test_scanner_does_not_inherit_credentials_or_registry_access(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic")
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic")
    prefix = (
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "assert 'GITHUB_TOKEN' not in os.environ\n"
        "assert os.environ['GOPROXY'] == 'off'\n"
    )
    runner, case, root, _ = _setup(tmp_path, prefix=prefix)
    assert runner.run(case, root)["valid_measurement"]


@pytest.mark.parametrize("timeout", [0, -1, 121, float("nan"), float("inf")])
def test_invalid_deadlines_cannot_run_a_scanner(tmp_path, timeout) -> None:
    runner, case, root, counter = _setup(tmp_path, timeout=timeout)
    with pytest.raises(ValueError, match="deadline"):
        runner.run(case, root)
    assert not counter.exists()


def test_no_unregistered_or_network_scanner_modes_are_constructed(tmp_path) -> None:
    with pytest.raises(ValueError, match="mode"):
        command(tmp_path / "scanner", tmp_path / "input", "cloud", tmp_path / "config")
    args = command(tmp_path / "scanner", tmp_path / "input", "verify", tmp_path / "config")
    assert "--no-dependency-hallucinations" in args
    assert "--no-behavior" in args
