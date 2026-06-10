"""Tests for deployment-archetype parsing and drift signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.deployment import declared_archetype
from consistency_check.types import Archetype, Repo

if TYPE_CHECKING:
    from pathlib import Path


def _repo(root: Path, language: str = "python") -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _write_readme(root: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(body, encoding="utf-8")


def test_declared_archetype_reads_token_from_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nStage: S3\nDeployment: site-local\n")
    assert declared_archetype(_repo(tmp_path)) is Archetype.SITE_LOCAL


def test_declared_archetype_all_three_tokens(tmp_path: Path) -> None:
    for token, expected in [
        ("remote-hostable", Archetype.REMOTE_HOSTABLE),
        ("site-local", Archetype.SITE_LOCAL),
        ("host-local", Archetype.HOST_LOCAL),
    ]:
        _write_readme(tmp_path, f"# x\n\n## Status\nDeployment: {token}\n")
        assert declared_archetype(_repo(tmp_path)) is expected


def test_declared_archetype_token_value_case_insensitive(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: SITE-LOCAL\n")
    assert declared_archetype(_repo(tmp_path)) is Archetype.SITE_LOCAL


def test_declared_archetype_none_when_no_token(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nStage: S3.\n")
    assert declared_archetype(_repo(tmp_path)) is None


def test_declared_archetype_none_without_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## License\nMIT\n")
    assert declared_archetype(_repo(tmp_path)) is None


def test_declared_archetype_none_when_readme_missing(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert declared_archetype(_repo(tmp_path)) is None


def test_declared_archetype_ignores_token_outside_status(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nStage: S3.\n\n## Notes\nDeployment: host-local\n")
    assert declared_archetype(_repo(tmp_path)) is None
