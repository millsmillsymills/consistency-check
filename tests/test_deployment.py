"""Tests for deployment-archetype parsing and drift signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.deployment import declared_archetype, deployment_drift_signal
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


def _write_src_file(root: Path, body: str) -> None:
    src = root / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "main.py").write_text(body, encoding="utf-8")


def test_drift_host_local_without_serial_dep(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: host-local\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["httpx==0.27.0"]\n', encoding="utf-8"
    )
    signal = deployment_drift_signal(_repo(tmp_path), Archetype.HOST_LOCAL)
    assert signal is not None
    assert "serial" in signal.lower()


def test_no_drift_host_local_with_serial_dep(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: host-local\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pyserial==3.5"]\n', encoding="utf-8"
    )
    assert deployment_drift_signal(_repo(tmp_path), Archetype.HOST_LOCAL) is None


def test_drift_remote_with_interactive_auth(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: remote-hostable\n")
    _write_src_file(tmp_path, "import getpass\npw = getpass.getpass()\n")
    signal = deployment_drift_signal(_repo(tmp_path), Archetype.REMOTE_HOSTABLE)
    assert signal is not None
    assert "interactive" in signal.lower()


def test_drift_site_local_that_looks_remote(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: site-local\n\nToken auth.\n")
    _write_src_file(tmp_path, 'BASE_URL = "https://api.example.com"\n')
    signal = deployment_drift_signal(_repo(tmp_path), Archetype.SITE_LOCAL)
    assert signal is not None
    assert "remote-hostable" in signal


def test_drift_site_local_detects_typed_url_constant(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nDeployment: site-local\n\nToken auth.\n")
    _write_src_file(tmp_path, 'API_URL: str = "https://api.example.com"\n')
    assert deployment_drift_signal(_repo(tmp_path), Archetype.SITE_LOCAL) is not None


def test_no_drift_site_local_with_host_env(tmp_path: Path) -> None:
    _write_readme(
        tmp_path,
        "# x\n\n## Status\nDeployment: site-local\n\nSet `UNRAID_HOST` to the appliance.\n",
    )
    _write_src_file(tmp_path, 'BASE_URL = "https://api.example.com"\n')
    assert deployment_drift_signal(_repo(tmp_path), Archetype.SITE_LOCAL) is None
