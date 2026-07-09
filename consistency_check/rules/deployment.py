"""Rules: deployment archetypes (MCP-DEPLOY-*) and their meta-rules.

Spec: docs/superpowers/specs/2026-06-10-mcp-deployment-scheme-design.md and
docs/standards/deployment.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.deployment import declared_archetype, deployment_drift_signal
from consistency_check.sources import combined_source_text
from consistency_check.types import Archetype, Rule, Stage, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

_ALL_ARCHETYPES = frozenset({Archetype.REMOTE_HOSTABLE, Archetype.SITE_LOCAL, Archetype.HOST_LOCAL})
_UNDECLARED = "no Deployment archetype declared"

_IMAGE_PUBLISH = re.compile(r"docker/build-push-action|docker push|ghcr\.io")
_WORKER_PUBLISH = re.compile(r"wrangler (deploy|publish)")
_RELEASE_ASSET = re.compile(r"softprops/action-gh-release|gh release upload|upload-release-asset")
_COMPOSE_FILES = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")


def _read(repo: Repo, *parts: str) -> str:
    """Read a file under the repo path; empty string when missing."""
    target = repo.path.joinpath(*parts)
    if not target.is_file():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


def _workflow_text(repo: Repo) -> str:
    wf_dir = repo.path / ".github" / "workflows"
    if not wf_dir.is_dir():
        return ""
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(wf_dir.iterdir())
        if p.suffix in {".yml", ".yaml"} and p.is_file()
    )


def _docs_text(repo: Repo) -> str:
    chunks = [_read(repo, "README.md")]
    docs = repo.path / "docs"
    if docs.is_dir():
        chunks.extend(
            p.read_text(encoding="utf-8", errors="replace") for p in sorted(docs.rglob("*.md"))
        )
    return "\n".join(chunks)


def _has_compose_example(repo: Repo) -> bool:
    if any((repo.path / name).is_file() for name in _COMPOSE_FILES):
        return True
    return re.search(r"(?i)docker (compose|run)", _docs_text(repo)) is not None


def _artifact_remote(repo: Repo, wf: str) -> str | None:
    has_container = (repo.path / "Dockerfile").is_file()
    has_worker = any(
        (repo.path / n).is_file() for n in ("wrangler.toml", "wrangler.jsonc", "wrangler.json")
    )
    if not (has_container or has_worker):
        return "no Dockerfile or wrangler config at repo root"
    if not (_IMAGE_PUBLISH.search(wf) or _WORKER_PUBLISH.search(wf)):
        return "no workflow step publishes the image or deploys the worker"
    return None


def _artifact_site(repo: Repo, wf: str) -> str | None:
    if not (repo.path / "Dockerfile").is_file():
        return "no Dockerfile at repo root"
    if not _has_compose_example(repo):
        return "no compose/run example (compose file or docker compose/run in docs)"
    if not _IMAGE_PUBLISH.search(wf):
        return "no workflow step pushes the image to a registry"
    return None


def _artifact_host(repo: Repo, wf: str) -> str | None:
    has_manifest = (repo.path / "manifest.json").is_file() or (
        repo.path / "mcpb" / "manifest.json"
    ).is_file()
    if not has_manifest:
        return "no MCPB manifest.json at repo root or mcpb/"
    if "mcpb" not in wf.lower() or not _RELEASE_ASSET.search(wf):
        return "no workflow builds the .mcpb and uploads it as a release asset"
    return None


def _check_artifact(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    wf = _workflow_text(repo)
    if arch is Archetype.REMOTE_HOSTABLE:
        return _artifact_remote(repo, wf)
    if arch is Archetype.SITE_LOCAL:
        return _artifact_site(repo, wf)
    return _artifact_host(repo, wf)


_HTTP_LISTENER = re.compile(r"streamable|sse_app|uvicorn|http_app|ListenAndServe")


def _check_transport(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    src = combined_source_text(repo)
    if arch is Archetype.REMOTE_HOSTABLE:
        if "streamable" not in src.lower():
            return "no streamable-HTTP transport option found in source"
        return None
    if arch is Archetype.HOST_LOCAL:
        listener = _HTTP_LISTENER.search(src)
        if listener is not None:
            return f"host-local server constructs a network listener ({listener.group(0)})"
        return None
    return None


def _check_registry(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    if arch is Archetype.SITE_LOCAL:
        return None
    if (repo.path / "server.json").is_file():
        return None
    readme = _read(repo, "README.md")
    if re.search(r"(?i)mcp registry|registry\.modelcontextprotocol\.io", readme):
        return None
    return "no server.json and no MCP-registry reference in README"


def _check_deploy_docs(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    text = _docs_text(repo)
    if arch is Archetype.REMOTE_HOSTABLE:
        ok = bool(re.search(r"(?i)deploy", text)) and bool(
            re.search(r"(?i)connector|custom url", text)
        )
        return None if ok else "no docs covering deploying the service and adding it as a connector"
    if arch is Archetype.SITE_LOCAL:
        ok = bool(re.search(r"(?i)docker (compose|run)", text))
        return None if ok else "no docs covering running the container (docker compose/run)"
    ok = bool(re.search(r"(?i)\.mcpb", text)) and bool(re.search(r"(?i)install", text))
    return None if ok else "no docs covering installing the .mcpb bundle"


def _check_deployment_declared(repo: Repo) -> str | None:
    if declared_archetype(repo) is None:
        return "README ## Status section declares no Deployment archetype token"
    return None


def _check_deployment_drift(repo: Repo) -> str | None:
    declared = declared_archetype(repo)
    if declared is None:
        return None
    return deployment_drift_signal(repo, declared)


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-DEPLOY-ARTIFACT",
        tier=Tier.MUST,
        statement="Archetype's distribution artifact is built and published",
        check=_check_artifact,
        min_stage=Stage.S4,
        applies_to_archetype=_ALL_ARCHETYPES,
    ),
    Rule(
        id="MCP-DEPLOY-DOCS",
        tier=Tier.MUST,
        statement="Deploy/install documentation matches the archetype",
        check=_check_deploy_docs,
        min_stage=Stage.S4,
        applies_to_archetype=_ALL_ARCHETYPES,
    ),
    Rule(
        id="MCP-DEPLOY-TRANSPORT",
        tier=Tier.MUST,
        statement="Transports offered match the archetype",
        check=_check_transport,
        min_stage=Stage.S4,
        applies_to_archetype=_ALL_ARCHETYPES,
    ),
    Rule(
        id="MCP-DEPLOY-REGISTRY",
        tier=Tier.MAY,
        statement="Artifact submitted to the MCP registry",
        check=_check_registry,
        min_stage=Stage.S4,
        applies_to_archetype=frozenset({Archetype.REMOTE_HOSTABLE, Archetype.HOST_LOCAL}),
    ),
    Rule(
        id="MCP-DEPLOY-DECL",
        tier=Tier.MAY,
        statement="README ## Status declares a deployment archetype",
        check=_check_deployment_declared,
        min_stage=Stage.S0,
    ),
    Rule(
        id="MCP-DEPLOY-DRIFT",
        tier=Tier.MAY,
        statement="Declared archetype matches the repo's cheap structural signals",
        check=_check_deployment_drift,
        min_stage=Stage.S0,
    ),
)
