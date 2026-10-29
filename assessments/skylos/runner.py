"""Bounded, resumable synthetic scanner observations with preserved raw evidence."""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assessments.skylos.corpus import digest, input_digest
from assessments.skylos.environment import file_hash
from assessments.skylos.results import ADAPTER_VERSION, validate_output


def command(scanner: Path, root: Path, mode: str, config: Path) -> list[str]:
    """Construct only local static modes, without models, uploads, or registry lookups."""
    if mode == "verify":
        return [
            str(scanner),
            "verify",
            str(root),
            "--format",
            "json",
            "--no-behavior",
            "--no-contract",
            "--no-dependency-hallucinations",
            "--no-security",
        ]
    if mode not in {"dead-code", "security", "quality"}:
        raise ValueError("unsupported scanner mode")
    args = [
        str(scanner),
        str(root),
        "--json",
        "--no-upload",
        "--no-clipboard",
        "--no-cache",
        "--no-provenance",
        "--config-file",
        str(config),
    ]
    return args + ({"security": ["--danger"], "quality": ["--quality"]}.get(mode, []))


def _process(
    args: list[str], environment: dict[str, str], timeout: float, root: Path
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            cwd=root,
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "code": None,
            "stdout": b"",
            "stderr": str(exc).encode(),
            "state": "error",
            "seconds": time.perf_counter() - started,
        }
    state = "exited"
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        state = "timeout"
    return {
        "code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "state": state,
        "seconds": time.perf_counter() - started,
    }


@dataclass(frozen=True)
class Runner:
    """One verified toolchain and evidence store; inputs must be disposable corpus units."""

    scanner: Path
    engine: Path
    identity: dict[str, Any]
    store: Path
    timeout: float = 120

    def run(
        self, case: dict[str, Any], root: Path, *, sample: int = 0, resume: bool = True
    ) -> dict[str, Any]:
        """Record a unit, reusing only complete, intact observations with identical keys."""
        if os.name != "posix" or not math.isfinite(self.timeout) or not 0 < self.timeout <= 120:
            raise ValueError("pilot requires POSIX process groups and a deadline in (0, 120]")
        if type(sample) is not int or sample < 0:
            raise ValueError("sample must be a nonnegative integer")
        root, store = root.absolute(), self.store.absolute()
        if root.is_symlink() or store.resolve().is_relative_to(root.resolve()):
            raise ValueError("evidence store must be outside the nonsymlinked disposable root")
        source = input_digest(root, case)
        if (
            file_hash(self.scanner) != self.identity["scanner_sha256"]
            or file_hash(self.engine) != self.identity["go_engine"]["sha256"]
        ):
            raise ValueError("verified scanner or engine changed")
        config = store / "trusted-empty.toml"
        store.mkdir(parents=True, exist_ok=True)
        config.write_text("# Pilot deliberately overrides target scan configuration.\n")
        args = command(self.scanner.absolute(), root, case["mode"], config)
        contract = {
            name: file_hash(Path(__file__).with_name(name))
            for name in ("runner.py", "results.py", "corpus.py", "environment.py")
        }
        key = digest(
            {
                "adapter": ADAPTER_VERSION,
                "contract": contract,
                "case": case,
                "source": source,
                "identity": self.identity,
                "command": args,
                "config": file_hash(config),
                "timeout": self.timeout,
                "sample": sample,
            }
        )
        if resume and (cached := self._resume(key, case)) is not None:
            return {**cached, "resumed": True}
        attempt = store / key / uuid.uuid4().hex
        attempt.mkdir(parents=True)
        receipt = store / key / "complete.json"
        rejected = resume and receipt.is_file()
        if rejected:
            (attempt / "rejected-receipt.bin").write_bytes(receipt.read_bytes())
        outcome = _process(args, self._environment(store), self.timeout, root)
        record = self._record(case, root, source, key, args, sample, outcome)
        record["resume_rejected"] = rejected
        self._persist(attempt, record, outcome)
        return {**record, "resumed": False}

    def _environment(self, store: Path) -> dict[str, str]:
        environment = {
            key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG") if key in os.environ
        }
        environment.update(
            {
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
                "SKYLOS_GO_BIN": str(self.engine.absolute()),
                "GOPROXY": "off",
                "GOSUMDB": "off",
                "GOWORK": "off",
                "GOTOOLCHAIN": "local",
                "GOCACHE": str(store / "go-cache"),
                "GOMODCACHE": str(store / "go-mod"),
                "XDG_CONFIG_HOME": str(store / "config"),
                "XDG_CACHE_HOME": str(store / "cache"),
            }
        )
        return environment

    def _record(
        self,
        case: dict[str, Any],
        root: Path,
        source: str,
        key: str,
        args: list[str],
        sample: int,
        outcome: dict[str, Any],
    ) -> dict[str, Any]:
        observation = None
        state = outcome["state"]
        reason = state
        if state == "exited":
            try:
                observation = validate_output(
                    outcome["stdout"], outcome["code"], case["mode"], case["language"]
                )
                state = observation["state"]
                reason = "validated output" if state == "complete" else "incomplete coverage"
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                state, reason = "invalid_output", str(exc)
        try:
            current = input_digest(root, case)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            state, reason = "input_changed", str(exc)
        else:
            if current != source:
                state, reason = "input_changed", "input digest changed"
        return {
            "schema_version": 1,
            "key": key,
            "case_id": case["id"],
            "sample": sample,
            "language": case["language"],
            "mode": case["mode"],
            "input_sha256": source,
            "case_sha256": digest(case),
            "environment_sha256": digest(self.identity),
            "adapter_version": ADAPTER_VERSION,
            "command": args,
            "state": state,
            "reason": reason,
            "valid_measurement": state == "complete",
            "exit_code": outcome["code"],
            "seconds": outcome["seconds"],
            "observation": observation,
        }

    def _persist(self, attempt: Path, record: dict[str, Any], outcome: dict[str, Any]) -> None:
        for channel in ("stdout", "stderr"):
            (attempt / f"{channel}.bin").write_bytes(outcome[channel])
        result = attempt / "result.json"
        result.write_text(json.dumps(record, indent=2) + "\n")
        if record["valid_measurement"]:
            receipt = {
                "attempt": attempt.name,
                "key": record["key"],
                "hashes": {
                    name: file_hash(attempt / name)
                    for name in ("result.json", "stdout.bin", "stderr.bin")
                },
            }
            pending = attempt / "receipt.json"
            pending.write_text(json.dumps(receipt))
            pending.replace(attempt.parent / "complete.json")

    def _resume(self, key: str, case: dict[str, Any]) -> dict[str, Any] | None:
        directory = self.store.absolute() / key
        try:
            receipt = json.loads((directory / "complete.json").read_text())
            if receipt["key"] != key or not isinstance(receipt["attempt"], str):
                return None
            if not all(character in "0123456789abcdef" for character in receipt["attempt"]):
                return None
            attempt = directory / receipt["attempt"]
            if any(
                file_hash(attempt / name) != receipt["hashes"][name]
                for name in ("result.json", "stdout.bin", "stderr.bin")
            ):
                return None
            record = json.loads((attempt / "result.json").read_text())
            observation = validate_output(
                (attempt / "stdout.bin").read_bytes(),
                record["exit_code"],
                case["mode"],
                case["language"],
            )
            if record["key"] == key and record["state"] == observation["state"] == "complete":
                return record
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            return None
        return None
