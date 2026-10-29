"""Tracked path serialization must agree with the filesystem and its consumers."""

from __future__ import annotations

import errno
import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from consistency_check._git import tracked_files
from consistency_check.rules.security import RULES as SECURITY_RULES
from consistency_check.rules.structure import RULES as STRUCTURE_RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "directory",
    [
        "café",
        "has space",
        "has\ttab",
        "has\nnewline",
        'has"quote',
        "has\\slash",
        os.fsdecode(b"bad-\xff"),
    ],
)
def test_tracked_unusual_paths_reach_content_checks(tmp_path: Path, directory: str) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    folder = tmp_path / directory
    try:
        folder.mkdir()
    except OSError as exc:
        if exc.errno == errno.EILSEQ:
            pytest.skip("filesystem rejects non-UTF-8 filenames")
        raise
    (folder / ".env").write_text("EXAMPLE=dummy-value\n", encoding="utf-8")
    (folder / "artifact.pyc").write_bytes(b"generated")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "--", directory], check=True)
    assert tracked_files(tmp_path) == frozenset({f"{directory}/.env", f"{directory}/artifact.pyc"})

    repo = Repo(name="sample", path=tmp_path, language="python", github_slug="o/sample")
    for rule in (*SECURITY_RULES, *STRUCTURE_RULES):
        if rule.id in {"MCP-019", "MCP-005"}:
            result = rule.check(repo)
            assert isinstance(result, str), f"{rule.id} must detect the tracked path"
            assert "dummy-value" not in result


def test_empty_git_index_is_distinct_from_unavailable_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert tracked_files(tmp_path) == frozenset()
