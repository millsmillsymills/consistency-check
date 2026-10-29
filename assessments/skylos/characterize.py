"""Capture pinned local capabilities and the separately registered suppression probes."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from assessments.skylos.corpus import digest, load_corpus, materialize
from assessments.skylos.environment import file_hash, verify_identity
from assessments.skylos.runner import Runner, capture_process

PLAN = Path(__file__).with_name("characterization-plan.json")
OUTPUT = Path("audit-out/skylos")


def diagnostic_commands(scanner: Path, engine: Path) -> list[tuple[str, list[str]]]:
    """Use only local help, engine identity, and doctor with hook self-tests disabled."""
    return [
        ("cli-help", [str(scanner), "--help"]),
        ("verify-help", [str(scanner), "verify", "--help"]),
        ("doctor", [str(scanner), "doctor", "--format", "json"]),
        ("engine-version", [str(engine), "--version"]),
    ]


def capture_capabilities(runner: Runner, root: Path) -> dict[str, Any]:
    """Preserve every raw diagnostic attempt before checking its exit or payload."""
    attempt = OUTPUT / "characterization" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    context = {
        "started_utc": datetime.now(UTC).isoformat(),
        "host_load_1_5_15": os.getloadavg(),
        "plan_sha256": file_hash(PLAN),
        "collector_sha256": file_hash(Path(__file__)),
        "environment_sha256": digest(runner.identity),
        "sample": 0,
        "hook_self_tests": "disabled",
    }
    (attempt / "context.json").write_text(json.dumps(context, indent=2) + "\n")
    environment = runner.environment(runner.store.absolute())
    environment["SKYLOS_HOOKS_DISABLE"] = "all"
    outcomes = {}
    for name, args in diagnostic_commands(runner.scanner.absolute(), runner.engine.absolute()):
        outcome = capture_process(args, environment, 120, root.absolute())
        for channel in ("stdout", "stderr"):
            (attempt / f"{name}.{channel}.bin").write_bytes(outcome[channel])
        outcomes[name] = {
            "command": args,
            "state": outcome["state"],
            "exit_code": outcome["code"],
            "seconds": outcome["seconds"],
            "stdout_sha256": file_hash(attempt / f"{name}.stdout.bin"),
        }
    (attempt / "diagnostics.json").write_text(json.dumps(outcomes, indent=2) + "\n")
    if any(item["state"] != "exited" or item["exit_code"] != 0 for item in outcomes.values()):
        raise ValueError("capability capture failed; raw evidence retained")
    doctor = json.loads((attempt / "doctor.stdout.bin").read_bytes())
    if (
        doctor.get("schema_version") != 1
        or doctor["checks"]["skylos"]["version"] != "5.1.5"
        or doctor["checks"]["go_engine"].get("status") != "available"
        or doctor["checks"]["go_engine"].get("binary") != str(runner.engine.absolute())
    ):
        raise ValueError("pinned scanner or selected native engine unavailable")
    required = {
        "cli-help": [
            "--json",
            "--no-upload",
            "--no-clipboard",
            "--no-cache",
            "--no-provenance",
            "--config-file",
            "--danger",
            "--quality",
        ],
        "verify-help": [
            "--format",
            "--no-behavior",
            "--no-contract",
            "--no-dependency-hallucinations",
            "--no-security",
        ],
    }
    for name, flags in required.items():
        help_text = (attempt / f"{name}.stdout.bin").read_text()
        if any(flag not in help_text for flag in flags):
            raise ValueError(f"registered flags absent from {name}")
    return {"attempt": str(attempt), "diagnostics": outcomes}


def main() -> None:
    """Characterize registered units only; never start the scored corpus automatically."""
    plan = json.loads(PLAN.read_text())
    corpus = load_corpus()
    identity = verify_identity(
        Path("assessments/skylos/environment-macos-arm64.json"),
        Path(".scratch/skylos-env"),
        Path(".scratch/skylos-go"),
        Path("assessments/skylos/requirements.lock"),
    )
    if plan["corpus_sha256"] != digest(corpus) or plan["environment_sha256"] != digest(identity):
        raise ValueError("registered characterization inputs or environment changed")
    runner = Runner(
        Path(".scratch/skylos-env/bin/skylos"),
        Path(".scratch/skylos-go"),
        identity,
        OUTPUT / "observations",
    )
    cases = plan["probes"] + [
        case for case in corpus["cases"] if case["id"] in plan["mode_case_ids"]
    ]
    roots = [OUTPUT / "inputs" / case["id"] for case in cases]
    for case, root in zip(cases, roots, strict=True):
        if not root.exists():
            materialize(case, root)
    capabilities = capture_capabilities(runner, roots[0])
    records = [runner.run(case, root) for case, root in zip(cases, roots, strict=True)]
    destination = Path(capabilities["attempt"]) / "units.json"
    destination.write_text(json.dumps(records, indent=2) + "\n")
    for record in records:
        print(json.dumps({key: record[key] for key in ("case_id", "state", "reason", "resumed")}))  # noqa: T201


if __name__ == "__main__":
    main()
