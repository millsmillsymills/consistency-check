"""Load and materialize the frozen synthetic pilot inputs without executing them."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

CORPUS = Path(__file__).with_name("corpus.json")
MODES = frozenset({"dead-code", "verify", "security", "quality"})


def digest(value: Any) -> str:
    """Hash canonical JSON, independent of formatting or mapping order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_corpus(path: Path = CORPUS) -> dict[str, Any]:
    """Validate case identities, balance, paths, and independently paired inputs."""
    corpus = json.loads(path.read_text())
    if corpus.get("schema_version") != 1 or corpus.get("revision") != 1:
        raise ValueError("unsupported corpus schema/revision")
    cases = corpus.get("cases", [])
    counts = Counter((case["language"], case["kind"]) for case in cases)
    expected = {
        (language, kind): 15 for language in ("python", "go") for kind in ("defect", "control")
    }
    if counts != expected or len({case["id"] for case in cases}) != 60:
        raise ValueError("corpus requires 15 defects and controls per language, with unique IDs")
    for case in cases:
        _validate_case(case)
    if len({digest(case["files"]) for case in cases}) != 60:
        raise ValueError("duplicate source inputs inflate the case count")
    return corpus


def _validate_case(case: dict[str, Any]) -> None:
    if not re.fullmatch(r"(?:python|go)-\d{2}-(?:defect|control)", case["id"]):
        raise ValueError("invalid case ID")
    if case["mode"] not in MODES or not case.get("ground_truth"):
        raise ValueError("case must declare a known mode and preregistered ground truth")
    if case.get("expected") != ("finding" if case["kind"] == "defect" else "no_finding"):
        raise ValueError("case expectation conflicts with its kind")
    files = case.get("files")
    if not isinstance(files, dict) or case.get("target_file") not in files:
        raise ValueError("case must contain its expected target file")
    for name, source in files.items():
        _validate_file(name, source)


def _validate_file(name: str, source: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
        raise ValueError("case paths must stay within the disposable root")
    if ".git" in path.parts or path.name in {".pilot-unit.json", ".gitattributes"}:
        raise ValueError("reserved pilot metadata path")
    if not isinstance(source, str):
        raise TypeError("source files must be text")


def materialize(case: dict[str, Any], root: Path) -> None:
    """Create a new disposable case directory; never overlay an existing checkout."""
    _validate_case(case)
    root.mkdir(parents=True, exist_ok=False)
    for name, source in case["files"].items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-f", "--", *case["files"])
    _git(root, "commit", "-qm", "Frozen synthetic pilot input")
    marker = {
        "case_sha256": digest(case),
        "files_sha256": digest(case["files"]),
        "head": _git(root, "rev-parse", "HEAD").strip(),
    }
    (root / ".pilot-unit.json").write_text(json.dumps(marker))


def _git(root: Path, *args: str) -> str:
    root = root.resolve()
    environment = {
        **{key: os.environ[key] for key in ("PATH", "LANG", "TMPDIR") if key in os.environ},
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }
    result = subprocess.run(
        [
            "git",
            f"--git-dir={root / '.git'}",
            f"--work-tree={root}",
            "-c",
            "core.fsmonitor=",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.attributesFile=/dev/null",
            "-c",
            "user.name=Pilot",
            "-c",
            "user.email=pilot@example.invalid",
            "-C",
            str(root),
            *args,
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return result.stdout


def input_digest(root: Path, case: dict[str, Any]) -> str:
    """Verify the disposable marker and every file; reject links and source drift."""
    marker = root / ".pilot-unit.json"
    if marker.is_symlink() or (root / ".git").is_symlink():
        raise ValueError("symlinked input marker")
    unit = json.loads(marker.read_text())
    if unit.get("files_sha256") != digest(case["files"]) or unit.get("case_sha256") != digest(case):
        raise ValueError("disposable input does not match the registered case")
    if _git(root, "rev-parse", "HEAD").strip() != unit.get("head"):
        raise ValueError("disposable Git context changed")
    expected = {**case["files"], ".pilot-unit.json": marker.read_text()}
    actual = _source_files(root)
    if actual != expected:
        raise ValueError("input changed since materialization")
    return digest(actual)


def _source_files(root: Path) -> dict[str, str]:
    actual = {}
    for path in root.rglob("*"):
        if path.relative_to(root).parts[0] == ".git":
            continue
        if path.is_symlink():
            raise ValueError("symlink in disposable input")
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = path.read_bytes().decode("utf-8")
    return actual
