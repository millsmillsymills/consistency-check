"""Environment changes invalidate benchmark identities before any scanner invocation."""

from __future__ import annotations

import json

import pytest
from assessments.skylos import environment as identity


def _environment(tmp_path, monkeypatch):
    environment = tmp_path / "environment"
    (environment / "bin").mkdir(parents=True)
    scanner = environment / "bin" / "skylos"
    scanner.write_bytes(b"launcher")
    engine = tmp_path / "engine"
    engine.write_bytes(b"native")
    lock = tmp_path / "requirements.lock"
    lock.write_text("skylos==5.1.5 --hash=sha256:artifact\n")
    package = {
        "name": "skylos",
        "version": "5.1.5",
        "sha256": "artifact",
        "installed_sha256": "payload",
    }
    manifest = {
        "schema_version": 1,
        "scanner_version": "5.1.5",
        "source_commit": identity.SOURCE_COMMIT,
        "lock_sha256": identity.file_hash(lock),
        "scanner_sha256": identity.file_hash(scanner),
        "go_engine": {
            "source_commit": identity.SOURCE_COMMIT,
            "sha256": identity.file_hash(engine),
        },
        "python": "3.13",
        "os": "Linux",
        "machine": "test",
        "packages": [package],
    }
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(identity, "_probe", lambda _path: manifest)
    return path, environment, engine, lock, manifest


def test_matching_payloads_are_accepted_without_installing_a_scanner(tmp_path, monkeypatch) -> None:
    path, environment, engine, lock, expected = _environment(tmp_path, monkeypatch)
    assert identity.verify_identity(path, environment, engine, lock) == expected


@pytest.mark.parametrize("changed", ["lock", "engine", "scanner", "package", "host", "source"])
def test_toolchain_drift_refuses_measurements(tmp_path, monkeypatch, changed) -> None:
    path, environment, engine, lock, actual = _environment(tmp_path, monkeypatch)
    if changed == "lock":
        lock.write_text("different")
    elif changed == "engine":
        engine.write_bytes(b"different")
    elif changed == "scanner":
        (environment / "bin" / "skylos").write_bytes(b"different")
    elif changed == "package":
        actual["packages"][0]["installed_sha256"] = "different"
    elif changed == "host":
        actual["os"] = "different"
    else:
        actual["source_commit"] = "different"
        path.write_text(json.dumps(actual))
    with pytest.raises(ValueError, match=r"changed|differs"):
        identity.verify_identity(path, environment, engine, lock)
