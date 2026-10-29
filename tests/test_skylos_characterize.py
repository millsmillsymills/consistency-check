"""Capability capture stays local, verifies selected engine/flags and retains failures."""

import json

import pytest
from assessments.skylos import characterize
from assessments.skylos.corpus import digest, load_corpus
from assessments.skylos.runner import Runner


def test_probe_registration_cannot_change_the_scored_corpus() -> None:
    plan = json.loads(characterize.PLAN.read_text())
    corpus = load_corpus()
    assert plan["corpus_sha256"] == digest(corpus)
    assert len(plan["probes"]) == 7
    assert len({case["id"] for case in plan["probes"]}) == 7
    assert not {case["id"] for case in plan["probes"]} & {case["id"] for case in corpus["cases"]}
    assert set(plan["mode_case_ids"]) <= {case["id"] for case in corpus["cases"]}


@pytest.mark.parametrize("failure", [None, "exit", "engine", "flags", "json"])
def test_diagnostics_disable_hooks_and_retain_every_raw_attempt(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(characterize, "OUTPUT", tmp_path)
    runner = Runner(tmp_path / "scanner", tmp_path / "engine", {}, tmp_path / "evidence")
    doctor = {
        "schema_version": 1,
        "checks": {
            "skylos": {"version": "5.1.5"},
            "go_engine": {"status": "available", "binary": str(runner.engine)},
        },
    }
    if failure == "engine":
        doctor["checks"]["go_engine"]["status"] = "unavailable"
    help_text = (
        "--json --no-upload --no-clipboard --no-cache --no-provenance --config-file "
        "--danger --quality --format --no-behavior --no-contract "
        "--no-dependency-hallucinations --no-security"
    )
    calls = []

    def capture(args, environment, timeout, root):
        assert environment["SKYLOS_HOOKS_DISABLE"] == "all"
        assert environment["SKYLOS_GO_BIN"] == str(runner.engine)
        assert timeout == 120
        assert root == tmp_path
        calls.append(args)
        stdout = b"" if failure == "flags" else help_text.encode()
        if "doctor" in args:
            stdout = b"{" if failure == "json" else json.dumps(doctor).encode()
        return {
            "stdout": stdout,
            "stderr": b"diagnostic",
            "code": 9 if failure == "exit" else 0,
            "state": "exited",
            "seconds": 0.1,
        }

    monkeypatch.setattr(characterize, "capture_process", capture)
    if failure:
        with pytest.raises(ValueError, match=r"capture failed|unavailable|flags|property name"):
            characterize.capture_capabilities(runner, tmp_path)
    else:
        assert len(characterize.capture_capabilities(runner, tmp_path)["diagnostics"]) == 4
    assert len(calls) == 4
    attempt = next((tmp_path / "characterization").iterdir())
    assert len(list(attempt.glob("*.stdout.bin"))) == 4
    assert len(list(attempt.glob("*.stderr.bin"))) == 4
    assert (attempt / "diagnostics.json").exists()
