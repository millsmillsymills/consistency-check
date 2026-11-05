"""Environment changes invalidate benchmark identities before any scanner invocation."""

from __future__ import annotations

import json

import pytest
from assessments.skylos import environment as identity
from assessments.skylos import preflight_python


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


def _python_preflight(tmp_path, monkeypatch):
    path, environment, engine, lock, manifest = _environment(tmp_path, monkeypatch)
    manifest.pop("go_engine")
    manifest.update(
        schema_version=2,
        purpose="python-identity-preflight",
        go_evaluation="deferred",
        collection_authorized=False,
    )
    path.write_text(json.dumps(manifest))
    engine.unlink()
    return path, environment, engine, lock, manifest


def test_python_preflight_needs_no_engine_and_cannot_enter_old_collector(tmp_path, monkeypatch):
    path, environment, engine, lock, manifest = _python_preflight(tmp_path, monkeypatch)
    assert identity.verify_python_preflight(path, environment, lock) == manifest
    with pytest.raises(ValueError, match="unsupported environment manifest"):
        identity.verify_identity(path, environment, engine, lock)


@pytest.mark.parametrize(
    "field", ["schema_version", "purpose", "go_evaluation", "collection_authorized"]
)
def test_python_preflight_refuses_incompatible_scope(tmp_path, monkeypatch, field):
    path, environment, _, lock, manifest = _python_preflight(tmp_path, monkeypatch)
    manifest[field] = "wrong"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Python-only"):
        identity.verify_python_preflight(path, environment, lock)


@pytest.mark.parametrize("changed", ["lock", "scanner", "package", "host", "source"])
def test_python_preflight_refuses_drift(tmp_path, monkeypatch, changed):
    path, environment, _, lock, actual = _python_preflight(tmp_path, monkeypatch)
    if changed == "lock":
        lock.write_text("changed")
    elif changed == "scanner":
        (environment / "bin" / "skylos").write_bytes(b"changed")
    elif changed == "package":
        actual["packages"][0]["installed_sha256"] = "changed"
    elif changed == "host":
        actual["os"] = "changed"
    else:
        actual["source_commit"] = "changed"
        path.write_text(json.dumps(actual))
    with pytest.raises(ValueError, match=r"changed|differs"):
        identity.verify_python_preflight(path, environment, lock)


def test_python_preflight_cli_reports_no_collection(tmp_path, monkeypatch, capsys):
    path, environment, _, lock, _ = _python_preflight(tmp_path, monkeypatch)
    assert (
        preflight_python.main(
            ["--identity", str(path), "--environment", str(environment), "--lock", str(lock)]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["collection_authorized"] is False
    assert result["go_evaluation"] == "deferred"
    assert result["state"] == "python_identity_verified"


@pytest.mark.parametrize("extra", [{"collection_authorized": True}, {"go_engine": {}}])
def test_python_preflight_rejects_collection_or_engine_claims(tmp_path, monkeypatch, extra):
    path, environment, _, lock, manifest = _python_preflight(tmp_path, monkeypatch)
    manifest.update(extra)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Python-only"):
        identity.verify_python_preflight(path, environment, lock)


def test_python_preflight_cli_failure_is_explicit(tmp_path, capsys):
    assert (
        preflight_python.main(
            ["--identity", str(tmp_path / "absent.json"), "--environment", str(tmp_path)]
        )
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "preflight_failed"
    assert "identity_sha256" not in result
