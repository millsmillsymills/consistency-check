# MCP Deployment Scheme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the deployment-archetype standard (spec: `docs/superpowers/specs/2026-06-10-mcp-deployment-scheme-design.md`) in the `consistency-check` auditor: an `Archetype` axis on rules, a `Deployment:` README token, four archetype-conditional `MCP-DEPLOY-*` rules at S4, two MAY-tier meta-rules, and MCP-018 retiered MAY→MUST.

**Architecture:** Mirrors the existing stage system exactly. Token parsing and drift signals live in a new `consistency_check/deployment.py` (parallel to `stage.py`); the six new rules live in a new `consistency_check/rules/deployment.py` (parallel to `rules/stage_meta.py`); the audit loop gains one archetype gate after the existing language and stage gates. Rules whose `applies_to_archetype` excludes the repo's declared archetype yield `FindingStatus.NA`.

**Tech Stack:** Python 3.13, `uv`, `pytest -q`, `ruff check`, `ty check`. All work happens in `~/Projects/consistency-check`.

**Three suite-wide invariants every task must respect** (these are enforced by existing tests and will go red if ignored):

1. **`tests/test_meta.py`** diffs implemented rule IDs against `###` headings in a hardcoded list of `docs/standards/` files. New rules must appear as doc headings *in the same commit* that registers them, the file list must gain `deployment.md`, and the heading regex must learn the `DEPLOY-` ID shape (Task 4 fixes the regex and list).
2. **`tests/test_sweep.py`** calls **every rule's check directly on the synthetic fixtures, bypassing the stage and archetype gates**. The `good_*` fixtures must pass every check; the `bad_*` fixtures must fail every non-exempt check. Each rule task therefore also updates `tests/fixtures/build.py` (good side) and, where a check cannot fail on the bad fixture, adds an exemption with an inline reason to `_CANNOT_FAIL` (precedent: `MCP-STAGE-DRIFT`).
3. **Each task ends with the FULL suite green** (`uv run pytest -q`), not just the task's own test file.

**Repo state note:** The spec is committed on branch `feat/proto-018-021-plugin-standards`. Create the working branch from there so the spec is present.

---

### Task 0: Branch setup

**Files:** none

- [ ] **Step 1: Create the working branch**

```bash
cd ~/Projects/consistency-check
git checkout feat/proto-018-021-plugin-standards
git checkout -b feat/deployment-scheme
```

- [ ] **Step 2: Verify the suite is green before touching anything**

Run: `uv run pytest -q`
Expected: all tests pass, exit 0. If not, stop and report — do not build on a red baseline.

---

### Task 1: `Archetype` enum and `Rule.applies_to_archetype` field

**Files:**
- Modify: `consistency_check/types.py` (add enum after `Stage`; add field to `Rule`)
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_types.py`:

```python
def test_archetype_values_match_readme_tokens() -> None:
    from consistency_check.types import Archetype

    assert Archetype.REMOTE_HOSTABLE.value == "remote-hostable"
    assert Archetype.SITE_LOCAL.value == "site-local"
    assert Archetype.HOST_LOCAL.value == "host-local"


def test_rule_applies_to_archetype_defaults_to_none() -> None:
    from consistency_check.types import Rule, Tier

    rule = Rule(id="X-001", tier=Tier.MAY, statement="x", check=lambda repo: None)
    assert rule.applies_to_archetype is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_types.py -q`
Expected: FAIL — `ImportError: cannot import name 'Archetype'`.

- [ ] **Step 3: Implement**

In `consistency_check/types.py`, add after the `Stage` class:

```python
class Archetype(StrEnum):
    """Deployment archetype. Locality axis, declared in the README ## Status section."""

    REMOTE_HOSTABLE = "remote-hostable"
    SITE_LOCAL = "site-local"
    HOST_LOCAL = "host-local"
```

In the `Rule` dataclass, add a field after `min_stage`:

```python
    applies_to_archetype: frozenset[Archetype] | None = None
```

(`None` means the rule is not archetype-conditional and runs for every repo.)

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add consistency_check/types.py tests/test_types.py
git commit -m "feat: add Archetype enum and Rule.applies_to_archetype field"
```

---

### Task 2: `status_section_text` helper + `declared_archetype` parser

**Files:**
- Modify: `consistency_check/stage.py` (extract `status_section_text`, reuse in `declared_stage`)
- Create: `consistency_check/deployment.py`
- Test: `tests/test_deployment.py` (new), `tests/test_stage.py` (unchanged — must stay green)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_deployment.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_deployment.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'consistency_check.deployment'`.

- [ ] **Step 3: Extract the status-section helper in `stage.py`**

In `consistency_check/stage.py`, add above `declared_stage` (keep `_STATUS_SECTION` where it is):

```python
def status_section_text(repo: Repo) -> str | None:
    """Return the body of the README ``## Status`` section, or None when absent."""
    readme = repo.path / "README.md"
    if not readme.is_file():
        return None
    section = _STATUS_SECTION.search(readme.read_text(encoding="utf-8", errors="replace"))
    return None if section is None else section.group(1)
```

Rewrite `declared_stage` to use it (replacing its body, keeping its docstring):

```python
def declared_stage(repo: Repo) -> Stage | None:
    """Read the repo's declared stage from the README ``## Status`` section.

    Returns the parsed Stage, or None when the README is missing, has no
    ``## Status`` section, or that section carries no S0-S4 token (unstaged).
    """
    section = status_section_text(repo)
    if section is None:
        return None
    token = _STAGE_TOKEN.search(section)
    if token is None:
        return None
    return Stage(f"S{token.group(1)}")
```

- [ ] **Step 4: Create `consistency_check/deployment.py`**

```python
"""Deployment-archetype parsing and drift signals.

Pure and side-effect-free: every function reads repo files and returns data.
Mirrors stage.py, which does the same for the maturity-stage axis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.stage import status_section_text
from consistency_check.types import Archetype

if TYPE_CHECKING:
    from consistency_check.types import Repo

_DEPLOYMENT_TOKEN = re.compile(
    r"(?i)\bdeployment:\s*(remote-hostable|site-local|host-local)\b"
)


def declared_archetype(repo: Repo) -> Archetype | None:
    """Read the declared deployment archetype from the README ``## Status`` section.

    Returns the parsed Archetype, or None when the README is missing, has no
    ``## Status`` section, or that section carries no Deployment token.
    """
    section = status_section_text(repo)
    if section is None:
        return None
    token = _DEPLOYMENT_TOKEN.search(section)
    if token is None:
        return None
    return Archetype(token.group(1).lower())
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (the `stage.py` refactor must not break existing stage tests).

- [ ] **Step 6: Commit**

```bash
git add consistency_check/stage.py consistency_check/deployment.py tests/test_deployment.py
git commit -m "feat: parse Deployment archetype token from README Status section"
```

---

### Task 3: Archetype gating in the audit loop

**Files:**
- Modify: `consistency_check/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_audit.py` (reuse the file's existing imports — it already imports `Repo`; add `FindingStatus` and `pytest` if not present). These tests reference `MCP-DEPLOY-*` rules that land in Tasks 4–5, so mark all three `@pytest.mark.xfail(strict=True, reason="MCP-DEPLOY rules land in a later commit")` for this task's commit; Task 4 removes the first two markers, Task 5 the third.

```python
@pytest.mark.xfail(strict=True, reason="MCP-DEPLOY rules land in a later commit")
def test_archetype_rule_na_when_undeclared(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S4\n", encoding="utf-8")
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    findings = {f.rule_id: f for f in audit_repo(repo)}
    assert findings["MCP-DEPLOY-ARTIFACT"].status is FindingStatus.NA
    assert "no Deployment archetype declared" in findings["MCP-DEPLOY-ARTIFACT"].evidence


@pytest.mark.xfail(strict=True, reason="MCP-DEPLOY rules land in a later commit")
def test_archetype_rule_runs_when_archetype_matches(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: site-local\n", encoding="utf-8"
    )
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    findings = {f.rule_id: f for f in audit_repo(repo)}
    assert findings["MCP-DEPLOY-ARTIFACT"].status is FindingStatus.FAIL


@pytest.mark.xfail(strict=True, reason="MCP-DEPLOY rules land in a later commit")
def test_archetype_rule_na_when_archetype_excluded(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: site-local\n", encoding="utf-8"
    )
    repo = Repo(name="x", path=tmp_path, language="python", github_slug="x/y")
    findings = {f.rule_id: f for f in audit_repo(repo)}
    assert findings["MCP-DEPLOY-REGISTRY"].status is FindingStatus.NA
    assert "site-local" in findings["MCP-DEPLOY-REGISTRY"].evidence
```

- [ ] **Step 2: Run to verify XFAIL, not ERROR**

Run: `uv run pytest tests/test_audit.py -q`
Expected: existing tests PASS; the three new tests XFAIL (they raise `KeyError` on the missing rule IDs, which xfail captures).

- [ ] **Step 3: Implement the gate in `audit.py`**

Add the import at the top of `consistency_check/audit.py`:

```python
from consistency_check.deployment import declared_archetype
```

In `audit_repo`, after `declared = declared_stage(repo)` add:

```python
    declared_arch = declared_archetype(repo)
```

Then insert a third gate inside the rule loop, after the existing stage gate (`if declared is not None and stage_rank(...)` block) and before the `try:`:

```python
        if rule.applies_to_archetype is not None:
            if declared_arch is None:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        tier=rule.tier,
                        status=FindingStatus.NA,
                        evidence="no Deployment archetype declared",
                        min_stage=rule.min_stage,
                    )
                )
                continue
            if declared_arch not in rule.applies_to_archetype:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        tier=rule.tier,
                        status=FindingStatus.NA,
                        evidence=f"not applicable to {declared_arch.value}",
                        min_stage=rule.min_stage,
                    )
                )
                continue
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS plus three XFAILs.

- [ ] **Step 5: Commit**

```bash
git add consistency_check/audit.py tests/test_audit.py
git commit -m "feat: gate archetype-conditional rules to NA in audit loop"
```

---

### Task 4: `MCP-DEPLOY-ARTIFACT` + `MCP-DEPLOY-DOCS` rules, doc skeleton, meta-test fix, fixture upgrade

This task registers the first archetype-conditional rules, which trips two suite invariants — so it also: (a) fixes `test_meta.py`'s regex and file list and creates `docs/standards/deployment.md` with the new rule headings, and (b) upgrades the good fixtures to declare an archetype and satisfy the new checks (which requires bumping them to `Stage: S4` with a SHA-pinned `release.yml`, or MCP-STAGE-DRIFT's ceiling check fires on the release pipeline).

**Files:**
- Create: `consistency_check/rules/deployment.py`
- Create: `docs/standards/deployment.md`
- Modify: `consistency_check/audit.py` (`_RULE_MODULES`)
- Modify: `tests/test_meta.py` (heading regex + file list)
- Modify: `tests/fixtures/build.py` (both `build_good_python` and `build_good_go`)
- Test: `tests/rules/test_deployment.py` (new)

- [ ] **Step 1: Write the failing rule tests**

Create `tests/rules/test_deployment.py`:

```python
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
        tmp_path, "release.yml",
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
        tmp_path, "release.yml",
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/rules/test_deployment.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'consistency_check.rules.deployment'`.

- [ ] **Step 3: Create `consistency_check/rules/deployment.py`**

Per-archetype helpers keep each function small (≤8 cyclomatic complexity):

```python
"""Rules: deployment archetypes (MCP-DEPLOY-*) and their meta-rules.

Spec: docs/superpowers/specs/2026-06-10-mcp-deployment-scheme-design.md and
docs/standards/deployment.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.deployment import declared_archetype
from consistency_check.types import Archetype, Rule, Stage, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo

_ALL_ARCHETYPES = frozenset(
    {Archetype.REMOTE_HOSTABLE, Archetype.SITE_LOCAL, Archetype.HOST_LOCAL}
)
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


def _check_deploy_docs(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    text = _docs_text(repo)
    if arch is Archetype.REMOTE_HOSTABLE:
        if re.search(r"(?i)deploy", text) and re.search(r"(?i)connector|custom url", text):
            return None
        return "no docs covering deploying the service and adding it as a connector"
    if arch is Archetype.SITE_LOCAL:
        if re.search(r"(?i)docker (compose|run)", text):
            return None
        return "no docs covering running the container (docker compose/run)"
    if re.search(r"(?i)\.mcpb", text) and re.search(r"(?i)install", text):
        return None
    return "no docs covering installing the .mcpb bundle"


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
)
```

- [ ] **Step 4: Register the module**

In `consistency_check/audit.py`, add to `_RULE_MODULES` before `"consistency_check.rules.stage_meta"`:

```python
    "consistency_check.rules.deployment",
```

- [ ] **Step 5: Fix `tests/test_meta.py`**

Two changes:

```python
_RULE_HEADING = re.compile(r"(?m)^###\s+([A-Z]+-(?:\d{3}|STAGE-[A-Z]+|DEPLOY-[A-Z]+))\b")
```

and add `"deployment.md"` to the file tuple in `_documented_ids`:

```python
    for f in ("mcp.md", "python.md", "go.md", "mcp-protocol.md", "stages.md", "deployment.md"):
```

- [ ] **Step 6: Create `docs/standards/deployment.md`**

Full intro plus the two rule sections implemented so far (Tasks 5–6 append theirs):

```markdown
# MCP Server Deployment Archetypes

The **deployment archetype** records where a server can run. It is declared per
repo and gates the archetype-conditional `MCP-DEPLOY-*` rules, all of which sit
at `min_stage = S4`. See
`docs/superpowers/specs/2026-06-10-mcp-deployment-scheme-design.md` for the full
design rationale.

## The three archetypes

- **`remote-hostable`** — no locality constraint; can run as a hosted
  streamable-HTTP endpoint or locally over stdio.
- **`site-local`** — bound to a site: must reach a network-private appliance,
  or cannot bootstrap unattended (interactive/stateful auth).
- **`host-local`** — bound to a host: requires physically attached hardware;
  never a network service.

## Decision tree (deterministic, in order)

1. Requires physically attached hardware (USB/serial)? → `host-local`
2. Backend not reachable from arbitrary networks (LAN appliance)? → `site-local`
3. Cannot bootstrap unattended from env config alone (interactive login,
   stateful session)? → `site-local`
4. Otherwise (portable token + publicly reachable backend) → `remote-hostable`

## Declaration

The README `## Status` section (MCP-007) carries a `Deployment:` token beside
the `Stage:` token:

```
Stage: S3
Deployment: site-local
```

Accepted tokens: `remote-hostable | site-local | host-local`. The auditor
grades against the declared token; an undeclared repo gets all
archetype-conditional rules as `n/a` plus the MCP-DEPLOY-DECL warning. A repo
may deliberately under-declare (ship a remote-capable server as a local tool);
MCP-DEPLOY-DRIFT surfaces the mismatch without blocking.

## Current assignments

| Server | Archetype | Deciding step |
|---|---|---|
| flipperzero-mcp | host-local | 1 — USB serial |
| unraid-mcp | site-local | 2 — LAN appliance |
| unifi-mcp | site-local | 2 — LAN controller |
| protonmail-mcp | site-local | 3 — interactive, stateful auth |
| gandi-mcp | remote-hostable | 4 |
| shortcut-mcp | remote-hostable | 4 |

## Rules (all `min_stage = S4`; `n/a` when the archetype does not match)

### MCP-DEPLOY-ARTIFACT — archetype's distribution artifact is built and published [MUST]

| Archetype | Required |
|---|---|
| remote-hostable | Dockerfile or wrangler config, plus a workflow step that publishes the image or deploys the worker |
| site-local | Dockerfile + compose/run example, plus a workflow step that pushes the image to a registry |
| host-local | MCPB `manifest.json`, plus a workflow that builds the `.mcpb` and uploads it as a release asset |

### MCP-DEPLOY-DOCS — deploy/install documentation matches the archetype [MUST]

| Archetype | Required docs (README or docs/) |
|---|---|
| remote-hostable | Deploying the service and adding it as a connector/custom URL |
| site-local | Running the container (`docker compose` / `docker run`) against the appliance |
| host-local | Installing the `.mcpb` bundle, including device prerequisites |
```

- [ ] **Step 7: Upgrade the good fixtures in `tests/fixtures/build.py`**

`test_sweep.py` calls every check directly, so both `build_good_python` and `build_good_go` must satisfy the new checks. Make these changes to **both** builders:

1. README `## Status`: change `Alpha. Stage: S3.` to `Alpha. Stage: S4.\nDeployment: site-local` (S4 because step 4 below adds a release pipeline, and MCP-STAGE-DRIFT's ceiling check flags a release pipeline on a declared S3 repo).
2. README: add an install line so MCP-DEPLOY-DOCS (site-local) passes, e.g. under an existing section: `Run with docker compose up -d.`
3. Add `Dockerfile` at fixture root: `FROM scratch\n` and `compose.yaml`: `services: {}\n`.
4. Add `.github/workflows/release.yml` — it must be SHA-pinned with a `# v` comment or MCP-017 fails on it:

```yaml
on:
  push:
    tags: ["v*"]
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@5cd11c3a4ced054e52742c5fd54dca954e0edd85  # v6
```

(The SHA need only be 40 hex chars to satisfy the pin-format check.)

The bad fixtures need no changes for these two rules: undeclared archetype makes both checks return evidence, so they correctly fail.

- [ ] **Step 8: Remove two xfail markers**

In `tests/test_audit.py`, delete the `@pytest.mark.xfail` lines from `test_archetype_rule_na_when_undeclared` and `test_archetype_rule_runs_when_archetype_matches`. Leave the marker on `test_archetype_rule_na_when_archetype_excluded` (references MCP-DEPLOY-REGISTRY, which lands in Task 5).

- [ ] **Step 9: Run the FULL suite**

Run: `uv run pytest -q`
Expected: PASS with one XFAIL. Pay attention to `tests/test_sweep.py` and `tests/test_meta.py` — if the sweep reports a good-fixture failure, the evidence string names exactly what the fixture is missing; fix the fixture, not the rule.

- [ ] **Step 10: Commit**

```bash
git add consistency_check/ tests/ docs/standards/deployment.md
git commit -m "feat: add MCP-DEPLOY-ARTIFACT and MCP-DEPLOY-DOCS rules"
```

---

### Task 5: `MCP-DEPLOY-TRANSPORT` and `MCP-DEPLOY-REGISTRY` rules

**Files:**
- Modify: `consistency_check/rules/deployment.py`
- Modify: `consistency_check/deployment.py` (add `source_text` — shared with drift in Task 6)
- Modify: `docs/standards/deployment.md` (append two rule sections)
- Modify: `tests/fixtures/build.py` (good fixtures gain `server.json`)
- Test: `tests/rules/test_deployment.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/rules/test_deployment.py`:

```python
# ── MCP-DEPLOY-TRANSPORT ──


def _write_src(root: Path, name: str, body: str) -> None:
    src = root / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / name).write_text(body, encoding="utf-8")


def test_transport_remote_requires_streamable_http(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    _write_src(tmp_path, "__main__.py", 'mcp.run(transport="stdio")\n')
    evidence = _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "streamable" in evidence.lower()


def test_transport_remote_passes_with_streamable(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    _write_src(
        tmp_path, "__main__.py",
        'transport = os.environ.get("MCP_TRANSPORT", "stdio")\n'
        'mcp.run(transport="streamable-http" if transport == "http" else "stdio")\n',
    )
    assert _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path)) is None


def test_transport_site_local_always_passes(tmp_path: Path) -> None:
    _scaffold(tmp_path, "site-local")
    _write_src(tmp_path, "__main__.py", 'mcp.run(transport="stdio")\n')
    assert _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path)) is None


def test_transport_host_local_fails_on_http_listener(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    _write_src(tmp_path, "__main__.py", "import uvicorn\nuvicorn.run(app)\n")
    evidence = _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path))
    assert evidence is not None
    assert "uvicorn" in evidence


def test_transport_host_local_passes_stdio_only(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    _write_src(tmp_path, "__main__.py", 'mcp.run(transport="stdio")\n')
    assert _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path)) is None


def test_transport_fails_when_archetype_undeclared(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S4\n", encoding="utf-8")
    assert _BY_ID["MCP-DEPLOY-TRANSPORT"].check(_repo(tmp_path)) is not None


# ── MCP-DEPLOY-REGISTRY ──


def test_registry_passes_with_server_json(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    (tmp_path / "server.json").write_text("{}\n", encoding="utf-8")
    assert _BY_ID["MCP-DEPLOY-REGISTRY"].check(_repo(tmp_path)) is None


def test_registry_passes_with_readme_mention(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    (tmp_path / "README.md").write_text(
        "# x\n\n## Status\nStage: S4\nDeployment: host-local\n\nListed on the MCP registry.\n",
        encoding="utf-8",
    )
    assert _BY_ID["MCP-DEPLOY-REGISTRY"].check(_repo(tmp_path)) is None


def test_registry_fails_when_absent(tmp_path: Path) -> None:
    _scaffold(tmp_path, "remote-hostable")
    assert _BY_ID["MCP-DEPLOY-REGISTRY"].check(_repo(tmp_path)) is not None


def test_registry_excludes_site_local() -> None:
    from consistency_check.types import Archetype

    rule = _BY_ID["MCP-DEPLOY-REGISTRY"]
    assert rule.applies_to_archetype == frozenset(
        {Archetype.REMOTE_HOSTABLE, Archetype.HOST_LOCAL}
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/rules/test_deployment.py -q`
Expected: FAIL — `KeyError: 'MCP-DEPLOY-TRANSPORT'`.

- [ ] **Step 3: Add `source_text` to `consistency_check/deployment.py`**

```python
_SOURCE_DIRS = ("src", "cmd", "internal")


def source_text(repo: Repo) -> str:
    """Concatenated text of all .py/.go files under the repo's source dirs."""
    chunks: list[str] = []
    for dirname in _SOURCE_DIRS:
        root = repo.path / dirname
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".go"}:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)
```

- [ ] **Step 4: Add the rules to `consistency_check/rules/deployment.py`**

Extend the import: `from consistency_check.deployment import declared_archetype, source_text`.

`_check_transport` returns evidence when the archetype is undeclared — the sweep's bad fixtures are undeclared and must fail every non-exempt rule:

```python
_HTTP_LISTENER = re.compile(r"streamable|sse_app|uvicorn|http_app|ListenAndServe")


def _check_transport(repo: Repo) -> str | None:
    arch = declared_archetype(repo)
    if arch is None:
        return _UNDECLARED
    source = source_text(repo)
    if arch is Archetype.REMOTE_HOSTABLE:
        if "streamable" not in source.lower():
            return "no streamable-HTTP transport option found in source"
        return None
    if arch is Archetype.HOST_LOCAL:
        listener = _HTTP_LISTENER.search(source)
        if listener is not None:
            return f"host-local server constructs a network listener ({listener.group(0)})"
        return None
    return None


def _check_registry(repo: Repo) -> str | None:
    if (repo.path / "server.json").is_file():
        return None
    readme = _read(repo, "README.md")
    if re.search(r"(?i)mcp registry|registry\.modelcontextprotocol\.io", readme):
        return None
    return "no server.json and no MCP-registry reference in README"
```

Append to `RULES`:

```python
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
```

- [ ] **Step 5: Append the two rule sections to `docs/standards/deployment.md`**

```markdown
### MCP-DEPLOY-TRANSPORT — transports offered match the archetype [MUST]

| Archetype | Transports |
|---|---|
| remote-hostable | stdio (default) and streamable HTTP behind a flag |
| site-local | stdio (default); HTTP behind a flag optional |
| host-local | stdio only; no network-listener code path |

Streamable HTTP specifically: SSE was superseded in the 2025-03-26 MCP spec
revision; new HTTP listeners must not use it.

### MCP-DEPLOY-REGISTRY — artifact submitted to the MCP registry [MAY]

Applies to `remote-hostable` and `host-local`; `n/a` for `site-local`.
Satisfied by a `server.json` registry manifest or an MCP-registry reference in
the README.
```

- [ ] **Step 6: Fixture and sweep accommodation**

- Good fixtures (both languages): add `server.json` at fixture root (`{}\n`) so the REGISTRY check passes when the sweep calls it directly (in real audits it is `n/a` for site-local, but the sweep bypasses the gate).
- TRANSPORT on good fixtures (site-local) returns `None` — nothing to add.
- Bad fixtures: undeclared archetype → TRANSPORT and REGISTRY both return evidence — they correctly fail; no `_CANNOT_FAIL` change.

- [ ] **Step 7: Remove the last xfail marker** in `tests/test_audit.py` (`test_archetype_rule_na_when_archetype_excluded`).

- [ ] **Step 8: Run the FULL suite**

Run: `uv run pytest -q`
Expected: PASS, no remaining XFAILs.

- [ ] **Step 9: Commit**

```bash
git add consistency_check/ tests/ docs/standards/deployment.md
git commit -m "feat: add MCP-DEPLOY-TRANSPORT and MCP-DEPLOY-REGISTRY rules"
```

---

### Task 6: Drift signals + meta-rules `MCP-DEPLOY-DECL` / `MCP-DEPLOY-DRIFT`

**Files:**
- Modify: `consistency_check/deployment.py` (drift signals)
- Modify: `consistency_check/rules/deployment.py` (meta-rules)
- Modify: `docs/standards/deployment.md` (append meta-rule sections)
- Modify: `tests/fixtures/build.py` (good READMEs gain a site marker)
- Modify: `tests/test_sweep.py` (`_CANNOT_FAIL` exemption for MCP-DEPLOY-DRIFT)
- Test: `tests/test_deployment.py`, `tests/rules/test_deployment.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deployment.py` (extend the existing imports to `from consistency_check.deployment import declared_archetype, deployment_drift_signal`):

```python
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


def test_no_drift_site_local_with_host_env(tmp_path: Path) -> None:
    _write_readme(
        tmp_path,
        "# x\n\n## Status\nDeployment: site-local\n\nSet `UNRAID_HOST` to the appliance.\n",
    )
    _write_src_file(tmp_path, 'BASE_URL = "https://api.example.com"\n')
    assert deployment_drift_signal(_repo(tmp_path), Archetype.SITE_LOCAL) is None
```

Append to `tests/rules/test_deployment.py`:

```python
# ── meta-rules ──


def test_decl_fires_when_no_deployment_token(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S3\n", encoding="utf-8")
    assert _BY_ID["MCP-DEPLOY-DECL"].check(_repo(tmp_path)) is not None


def test_decl_passes_when_declared(tmp_path: Path) -> None:
    _scaffold(tmp_path, "site-local")
    assert _BY_ID["MCP-DEPLOY-DECL"].check(_repo(tmp_path)) is None


def test_drift_rule_silent_when_undeclared(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S3\n", encoding="utf-8")
    assert _BY_ID["MCP-DEPLOY-DRIFT"].check(_repo(tmp_path)) is None


def test_drift_rule_fires_on_contradiction(tmp_path: Path) -> None:
    _scaffold(tmp_path, "host-local")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["httpx==0.27.0"]\n', encoding="utf-8"
    )
    assert _BY_ID["MCP-DEPLOY-DRIFT"].check(_repo(tmp_path)) is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_deployment.py tests/rules/test_deployment.py -q`
Expected: FAIL — `ImportError: cannot import name 'deployment_drift_signal'` and `KeyError: 'MCP-DEPLOY-DECL'`.

- [ ] **Step 3: Implement drift signals in `consistency_check/deployment.py`**

```python
_SERIAL_DEP = re.compile(r"(?i)serial|usb|hid")
_INTERACTIVE = re.compile(r"getpass|\binput\(")
_DEFAULT_PUBLIC_URL = re.compile(r"(?i)url\w*\"?\s*[:=]+\s*f?[\"']https://")
_SITE_MARKER = re.compile(r"(?i)_HOST\b|\bcontroller\b|\bappliance\b|\blan\b")


def _manifest_text(repo: Repo) -> str:
    chunks: list[str] = []
    for name in ("pyproject.toml", "go.mod"):
        path = repo.path / name
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def deployment_drift_signal(repo: Repo, declared: Archetype) -> str | None:
    """Return a one-line drift description when cheap signals contradict ``declared``.

    Coarse static checks only; catches obvious contradictions, not a full re-audit.
    """
    source = source_text(repo)
    if declared is Archetype.HOST_LOCAL and not _SERIAL_DEP.search(_manifest_text(repo)):
        return "declared host-local but no serial/USB dependency in the manifest"
    if declared is Archetype.REMOTE_HOSTABLE and _INTERACTIVE.search(source):
        return "declared remote-hostable but source prompts for interactive input at startup"
    if declared in (Archetype.SITE_LOCAL, Archetype.HOST_LOCAL):
        readme = repo.path / "README.md"
        readme_text = (
            readme.read_text(encoding="utf-8", errors="replace") if readme.is_file() else ""
        )
        if (
            _DEFAULT_PUBLIC_URL.search(source)
            and not _INTERACTIVE.search(source)
            and not _SITE_MARKER.search(readme_text)
        ):
            return (
                f"declared {declared.value} but the backend looks like a public cloud API "
                "with token auth (looks remote-hostable)"
            )
    return None
```

(For host-local the serial check fires first and returns — the looks-remote
signal only reaches host-local repos that do have a serial dep, which is the
correct precedence.)

- [ ] **Step 4: Add meta-rules to `consistency_check/rules/deployment.py`**

Extend the import: `from consistency_check.deployment import declared_archetype, deployment_drift_signal, source_text`.

```python
def _check_deployment_declared(repo: Repo) -> str | None:
    if declared_archetype(repo) is None:
        return "README ## Status section declares no Deployment archetype token"
    return None


def _check_deployment_drift(repo: Repo) -> str | None:
    declared = declared_archetype(repo)
    if declared is None:
        return None
    return deployment_drift_signal(repo, declared)
```

Append to `RULES` (no `applies_to_archetype` — meta-rules run for every repo; `min_stage=Stage.S0` mirrors the stage meta-rules):

```python
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
```

- [ ] **Step 5: Append the meta-rule sections to `docs/standards/deployment.md`**

```markdown
## Meta-rules

### MCP-DEPLOY-DECL — README declares a deployment archetype [MAY]

Fires when the `## Status` section carries no `Deployment:` token.

### MCP-DEPLOY-DRIFT — declared archetype matches repo signals [MAY]

Cheap structural contradictions only:

- `host-local` with no serial/USB dependency in the manifest
- `remote-hostable` whose source prompts for interactive input
- `site-local`/`host-local` whose source defaults to a public cloud base URL
  with no interactive auth and no site marker (`*_HOST` env var, "controller",
  "appliance", "LAN") in the README
```

- [ ] **Step 6: Fixture and sweep accommodation**

- Good fixtures (both languages): the DRIFT check must return `None`. The declared archetype is site-local; if the fixture source assigns a default `https://` URL, the looks-remote signal fires unless the README carries a site marker. Add a line to both good READMEs, e.g. `Set EXAMPLE_HOST to the appliance address.` (matches `_SITE_MARKER` via `_HOST`).
- `tests/test_sweep.py`: the bad fixtures are undeclared, so `_check_deployment_drift` returns `None` and cannot fail — same situation as `MCP-STAGE-DRIFT`. Add `"MCP-DEPLOY-DRIFT"` to both language sets in `_CANNOT_FAIL` and extend the explanatory comment block:

```python
#   MCP-DEPLOY-DRIFT cannot fire on the bad fixtures: they declare no
#                    archetype, so the drift check returns None (it only
#                    compares against a declared archetype). MCP-DEPLOY-DECL
#                    still fails them.
```

- [ ] **Step 7: Run the FULL suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add consistency_check/ tests/ docs/standards/deployment.md
git commit -m "feat: add deployment drift signals and DECL/DRIFT meta-rules"
```

---

### Task 7: Retier MCP-018 MAY → MUST with strengthened check

There are **no existing MCP-018 tests** in `tests/rules/test_ci.py` (verified: `rg -n "018" tests/rules/test_ci.py` is empty) — this task adds the first ones. The good fixtures already carry a publishing `release.yml` from Task 4, so they keep passing; the bad fixtures have no `release.yml` and keep failing.

**Files:**
- Modify: `consistency_check/rules/ci.py` (`_check_release_workflow` at ~line 130; rule registration at ~line 170)
- Modify: `docs/standards/mcp.md` (MCP-018 section — tier and check text must match the code)
- Test: `tests/rules/test_ci.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/rules/test_ci.py`, adapting to that file's existing helper conventions (check how it builds repos and indexes rules; if it has no `_BY_ID`, add `_BY_ID = {r.id: r for r in RULES}` using its existing `RULES` import):

```python
def test_mcp_018_fails_without_publish_step(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "release.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - run: echo built\n", encoding="utf-8"
    )
    evidence = _BY_ID["MCP-018"].check(_repo(tmp_path))
    assert evidence is not None
    assert "artifact" in evidence


def test_mcp_018_passes_with_image_push(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "release.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - uses: docker/build-push-action@abc\n", encoding="utf-8"
    )
    assert _BY_ID["MCP-018"].check(_repo(tmp_path)) is None


def test_mcp_018_fails_when_workflow_missing(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert _BY_ID["MCP-018"].check(_repo(tmp_path)) is not None


def test_mcp_018_contributing_fallback_removed(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CONTRIBUTING.md").write_text("## Release\nTag and push.\n", encoding="utf-8")
    assert _BY_ID["MCP-018"].check(_repo(tmp_path)) is not None


def test_mcp_018_is_must_tier() -> None:
    assert _BY_ID["MCP-018"].tier is Tier.MUST
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/rules/test_ci.py -q`
Expected: the new tests FAIL (old check passes a bare `release.yml` and the CONTRIBUTING fallback; tier is MAY).

- [ ] **Step 3: Implement**

In `consistency_check/rules/ci.py`, replace `_check_release_workflow`:

```python
_PUBLISH_MARKER = re.compile(
    r"docker/build-push-action|docker push|ghcr\.io|wrangler (deploy|publish)"
    r"|softprops/action-gh-release|gh release upload|upload-release-asset|\.mcpb"
)


def _check_release_workflow(repo: Repo) -> str | None:
    release = repo.path / ".github" / "workflows" / "release.yml"
    if not release.is_file():
        return "no .github/workflows/release.yml"
    text = release.read_text(encoding="utf-8", errors="replace")
    if not _PUBLISH_MARKER.search(text):
        return (
            "release.yml publishes no recognizable distribution artifact "
            "(no image push, wrangler deploy, or release-asset upload)"
        )
    return None
```

Update the registration: `tier=Tier.MUST` and
`statement="Release workflow builds and publishes the distribution artifact"`.

- [ ] **Step 4: Update `docs/standards/mcp.md` MCP-018 section** (same commit — doc and code must not drift):

```markdown
### MCP-018 — Release workflow builds and publishes the distribution artifact [MUST]

**Rationale.** At S4 (this rule's min_stage) the stage definition is "release
pipeline and versioned releases"; the workflow must produce the deployment
archetype's artifact, not merely exist. Retiered from MAY when the deployment
scheme landed — see `deployment.md`.

**Mechanical check.** `.github/workflows/release.yml` exists and contains a
publish step: `docker/build-push-action`, `docker push`, `ghcr.io`,
`wrangler deploy|publish`, a release-asset upload action, or an `.mcpb` build.
```

- [ ] **Step 5: Run the FULL suite**

Run: `uv run pytest -q`
Expected: PASS. The good fixtures pass via their Task 4 `release.yml`; the bad fixtures fail MCP-018 as before (no `release.yml`).

- [ ] **Step 6: Commit**

```bash
git add consistency_check/rules/ci.py tests/rules/test_ci.py docs/standards/mcp.md
git commit -m "feat: retier MCP-018 MAY->MUST; release workflow must publish the artifact"
```

---

### Task 8: Pin the min_stage map; refresh snapshots; lint and types

**Files:**
- Modify: `tests/test_min_stage_map.py`
- Possibly modify: `tests/__snapshots__/test_report.ambr` (regenerate if report output changed)

- [ ] **Step 1: Extend the expected map**

In `tests/test_min_stage_map.py`, add to `_EXPECTED`:

```python
    "MCP-DEPLOY-ARTIFACT": Stage.S4,
    "MCP-DEPLOY-DOCS": Stage.S4,
    "MCP-DEPLOY-TRANSPORT": Stage.S4,
    "MCP-DEPLOY-REGISTRY": Stage.S4,
    "MCP-DEPLOY-DECL": Stage.S0,
    "MCP-DEPLOY-DRIFT": Stage.S0,
```

- [ ] **Step 2: Run the full suite; refresh snapshots if needed**

Run: `uv run pytest -q`
If `tests/test_report.py` snapshot tests fail because reports now include the new rules: `uv run pytest tests/test_report.py --snapshot-update`, then **review the `.ambr` diff** (`git diff tests/__snapshots__/`) and confirm the only changes are the six new rule IDs appearing — anything else means a behavior regression, not a snapshot refresh.

- [ ] **Step 3: Lint and type-check**

Run: `uv run ruff check . && uv run ruff format --check . && uv run ty check`
Expected: clean. Fix every warning (zero-warnings policy).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: pin min_stage map for deployment rules; refresh snapshots"
```

---

### Task 9: Update `stages.md`

**Files:**
- Modify: `docs/standards/stages.md`

- [ ] **Step 1: Three edits**

1. S4 ladder entry — replace:
   `- **S4 Distributed** — deployment model wired plus a release pipeline and versioned releases.`
   with:
   `- **S4 Distributed** — declared deployment archetype satisfied (see deployment.md): distribution artifact built and published, deploy docs, matching transports, release pipeline.`
2. min_stage map S4 row — replace `| S4 | MCP-018 |` with:
   `| S4 | MCP-018, MCP-DEPLOY-ARTIFACT, MCP-DEPLOY-DOCS, MCP-DEPLOY-TRANSPORT, MCP-DEPLOY-REGISTRY |`
3. In the `## Meta-rules` section, add after the two stage meta-rules:
   `The deployment meta-rules (MCP-DEPLOY-DECL, MCP-DEPLOY-DRIFT) are defined in deployment.md and are likewise S0/MAY.`

- [ ] **Step 2: Verify doc-pinning tests**

Run: `uv run pytest tests/test_meta.py tests/test_min_stage_map.py -q`
Expected: PASS (the meta test reads rule IDs from `###` headings; the prose edits above add none).

- [ ] **Step 3: Commit**

```bash
git add docs/standards/stages.md
git commit -m "docs: point stages.md S4 at the deployment archetype standard"
```

---

### Task 10: Full verification + live smoke audit

**Files:** none (verification only)

- [ ] **Step 1: Full suite, lint, types**

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

Expected: all clean, zero warnings.

- [ ] **Step 2: Smoke-audit two real repos**

```bash
uv run consistency-check audit --repo unraid-mcp
uv run consistency-check audit --repo gandi-mcp
```

Expected for both (no `Deployment:` token declared yet):
- `MCP-DEPLOY-ARTIFACT/DOCS/TRANSPORT/REGISTRY` → `n/a` ("no Deployment archetype declared")
- `MCP-DEPLOY-DECL` → fail (MAY-tier warning; MAY never sets a nonzero exit code)
- `MCP-DEPLOY-DRIFT` → pass (silent when undeclared)
- MCP-018 → `n/a` (both repos declare S3; the rule's min_stage is S4)
- **Exit codes must not change** for any repo versus the pre-change auditor: every new MUST sits at S4 or behind the archetype gate, and no workspace repo declares S4. If an exit code differs, investigate before proceeding — do not assume it's benign.

- [ ] **Step 3: Confirm clean tree, then finish the branch**

```bash
git status --short   # must be clean
```

Use the superpowers:finishing-a-development-branch skill: push `feat/deployment-scheme` and open a PR against the repo's default branch (note: branched from `feat/proto-018-021-plugin-standards` — if that PR hasn't merged, mark this PR as stacked on it in the description).

---

## Out of scope for this plan

Adding `Deployment:` tokens to the six server READMEs and closing each server's
S4 gap (Dockerfiles, release workflows, `.mcpb` builds) is per-server work that
follows once this standard lands — one PR per server repo, not part of the
auditor change.
