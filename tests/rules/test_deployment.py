"""Tests for the deployment archetype rules (MCP-DEPLOY-*)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.deployment import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path

_BY_ID = {r.id: r for r in RULES}


def _repo(root: Path, language: str = "python") -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _scaffold(root: Path, archetype: str, stage: str = "S4") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        f"# x\n\n## Status\nStage: {stage}\nDeployment: {archetype}\n", encoding="utf-8"
    )


def _write_workflow(root: Path, name: str, body: str) -> None:
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / name).write_text(body, encoding="utf-8")


# ── MCP-DEPLOY-ARTIFACT ──


def test_artifact_remote_passes_with_dockerfile_and_push(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    (tmp_path / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    _write_workflow(
        tmp_path,
        "release.yml",
        "on: push\njobs:\n  r:\n    steps:\n      - uses: docker/build-push-action@abc\n",
    )
    assert _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path)) is None


def test_artifact_remote_fails_without_container_def(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    evidence = _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "Dockerfile" in evidence


def test_artifact_remote_passes_with_wrangler(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    (tmp_path / "wrangler.toml").write_text('name = "x"\n', encoding="utf-8")
    _write_workflow(tmp_path, "release.yml", "steps:\n  - run: npx wrangler deploy\n")
    assert _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path)) is None


def test_artifact_site_local_requires_compose_example(tmp_path: Path) -> None:
    _scaffold(tmp_path, "site-local")
    (tmp_path / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    _write_workflow(tmp_path, "release.yml", "steps:\n  - run: docker push ghcr.io/x/y\n")
    evidence = _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "compose" in evidence


def test_artifact_site_local_passes_complete(tmp_path: Path) -> None:
    _scaffold(tmp_path, "site-local")
    (tmp_path / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    _write_workflow(tmp_path, "release.yml", "steps:\n  - run: docker push ghcr.io/x/y\n")
    assert _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path)) is None


def test_artifact_host_local_requires_mcpb_manifest(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    evidence = _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "manifest.json" in evidence


def test_artifact_host_local_passes_complete(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    (tmp_path / "manifest.json").write_text("{}\n", encoding="utf-8")
    _write_workflow(
        tmp_path,
        "release.yml",
        "steps:\n  - run: mcpb pack\n  - uses: softprops/action-gh-release@abc\n",
    )
    assert _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path)) is None


def test_artifact_fails_when_archetype_undeclared(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S4\n", encoding="utf-8")
    evidence = _BY_ID["MCP-DEPLOY-ARTIFACT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "no Deployment archetype declared" in evidence


# ── MCP-DEPLOY-DOCS ──


def test_docs_remote_requires_deploy_and_connector(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    assert _BY_ID["MCP-DEPLOY-DOCS"].check(_repo(tmp_path)) is not None


def test_docs_remote_passes(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: remote-hostable\n\n"
        "## Deploy\nDeploy with `docker push`, then add as a custom connector.\n",
        encoding="utf-8",
    )
    assert _BY_ID["MCP-DEPLOY-DOCS"].check(_repo(tmp_path)) is None


def test_docs_site_local_passes_with_compose_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, "site-local")
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: site-local\n\n"
        "## Install\nRun `docker compose up -d` next to the appliance.\n",
        encoding="utf-8",
    )
    assert _BY_ID["MCP-DEPLOY-DOCS"].check(_repo(tmp_path)) is None


def test_docs_host_local_requires_mcpb_install_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    assert _BY_ID["MCP-DEPLOY-DOCS"].check(_repo(tmp_path)) is not None
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: host-local\n\n"
        "## Install\nDownload the .mcpb from the release and install; plug the device in first.\n",
        encoding="utf-8",
    )
    assert _BY_ID["MCP-DEPLOY-DOCS"].check(_repo(tmp_path)) is None
