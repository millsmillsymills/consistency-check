"""Verify the installed assessment toolchain against its recorded payload hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

SOURCE_COMMIT = "4f32409b5aaf913ca249483dc15221118c6c56db"
_PROBE = """
import hashlib, importlib.metadata, json, platform, re
packages = []
for dist in importlib.metadata.distributions():
    files = [(str(p), hashlib.sha256(dist.locate_file(p).read_bytes()).hexdigest())
             for p in sorted(dist.files, key=str) if p.hash is not None]
    tree_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    packages.append({"name": re.sub(r"[-_.]+", "-", dist.metadata["Name"].lower()),
                     "version": dist.version,
                     "installed_sha256": tree_hash})
print(json.dumps({"python": platform.python_version(), "os": platform.system(),
                  "os_release": platform.release(),
                  "machine": platform.machine(), "packages": packages}))
"""


def file_hash(path: Path) -> str:
    """Hash a file's bytes without relying on modification time."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _probe(python: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(python), "-c", _PROBE], capture_output=True, check=True, timeout=30
    )
    return json.loads(result.stdout)


def verify_identity(manifest: Path, environment: Path, engine: Path, lock: Path) -> dict[str, Any]:
    """Refuse changed binaries, dependencies, lockfiles, hosts, or source identities."""
    expected = json.loads(manifest.read_text())
    if expected.get("schema_version") != 1 or expected.get("scanner_version") != "5.1.5":
        raise ValueError("unsupported environment manifest")
    if expected.get("source_commit") != SOURCE_COMMIT:
        raise ValueError("scanner source revision differs from preregistration")
    if expected.get("lock_sha256") != file_hash(lock):
        raise ValueError("dependency lock changed")
    if expected.get("scanner_sha256") != file_hash(environment / "bin" / "skylos"):
        raise ValueError("scanner launcher changed")
    native = expected.get("go_engine", {})
    if native.get("source_commit") != SOURCE_COMMIT or native.get("sha256") != file_hash(engine):
        raise ValueError("native Go engine missing or changed")
    actual = _probe(environment / "bin" / "python")
    _verify_packages(expected, actual, lock.read_text())
    for field in ("python", "os", "os_release", "machine"):
        if expected.get(field) != actual.get(field):
            raise ValueError(f"assessment host changed: {field}")
    return expected


def _verify_packages(expected: dict[str, Any], actual: dict[str, Any], lock: str) -> None:
    wanted = {
        item["name"]: (item["version"], item["installed_sha256"]) for item in expected["packages"]
    }
    found = {
        item["name"]: (item["version"], item["installed_sha256"]) for item in actual["packages"]
    }
    if wanted != found or wanted.get("skylos", (None,))[0] != "5.1.5":
        raise ValueError("installed dependency payloads changed")
    if any(f"sha256:{item['sha256']}" not in lock for item in expected["packages"]):
        raise ValueError("artifact hash not present in dependency lock")
