# MCP Server Maturity Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an S0–S4 maturity-stage axis to `consistency-check` — declared per repo in the README `## Status` section, used to scope which rules apply and to report promotion gates — plus the doctrine doc and the `build-mcp-server` S0 on-ramp.

**Architecture:** A new `Stage` enum and a `min_stage` field on every `Rule` and `Finding`. A pure `stage.py` module parses the declared stage from the README, parses `SCOPE.md`, and computes drift signals. The audit driver skips rules above the declared stage (recording them `n/a`); two new MAY-tier meta-rules (`MCP-STAGE-DECL`, `MCP-STAGE-DRIFT`) surface unstaged/contradictory repos without failing a clean audit. The report gains a `## Stage` section. The ladder + per-rule `min_stage` map is documented in `docs/standards/stages.md` and guarded by the existing docs↔code meta-test.

**Tech Stack:** Python 3.13, `uv`, `pytest` (+ `syrupy` snapshots, `hypothesis`), `ruff`, `ty`. No new dependencies.

**Source of truth:** `docs/superpowers/specs/2026-06-01-mcp-maturity-ladder-design.md`.

**Branch:** `docs/mcp-maturity-ladder` (already checked out; the spec lives here).

---

## File map

Created:
- `consistency_check/stage.py` — stage parsing, `SCOPE.md` parsing, drift signals, ordering helpers.
- `consistency_check/rules/stage_meta.py` — the two MAY-tier meta-rules.
- `docs/standards/stages.md` — the ladder doctrine + `min_stage` map (rubric source of truth).
- `tests/test_stage.py` — unit tests for `stage.py`.
- `tests/rules/test_stage_meta.py` — tests for the meta-rules.

Modified:
- `consistency_check/types.py` — add `Stage`; add `min_stage` to `Rule` and `Finding`.
- `consistency_check/audit.py` — stage-filter rules; stamp `min_stage` onto findings; register the new rule module.
- `consistency_check/report.py` — render the `## Stage` section.
- `consistency_check/__main__.py` — pass `declared_stage(repo)` into `render_umbrella`.
- `consistency_check/filer.py` — pass `declared_stage(repo)` into its `render_umbrella` call (the `--apply` path).
- `consistency_check/rules/{structure,docs,security,ci,deps,mcp_protocol}.py` — set `min_stage` on the rules named in the ladder.
- `tests/test_meta.py` — scan `stages.md`; accept `MCP-STAGE-*` headings.
- `tests/fixtures/build.py` — declare a stage in the good fixtures' README.
- `tests/test_sweep.py` — exempt `MCP-STAGE-DRIFT` on the unstaged bad fixtures.
- `tests/test_report.py` — refresh snapshot; add a staged-report test.
- `~/Projects/mcp-server-dev-defaults/CLAUDE.md` — doctrine pointer (workspace `CLAUDE.md` symlink target).
- `build-mcp-server` `SKILL.md` — Phase 0 docs-first on-ramp (see Task 12 caveat about the plugin-cache path).

## min_stage assignment (authoritative for this plan)

Closure rule from the spec: any rule not listed below defaults to `S3`; deployment/release rules are `S4`.

| Stage | Rules (module) |
|---|---|
| S0 | MCP-001, MCP-002, MCP-005, MCP-006 (`structure.py`); MCP-007, MCP-009, MCP-010 (`docs.py`); MCP-019, MCP-020 (`security.py`) |
| S1 | PROTO-001, PROTO-002, PROTO-003, PROTO-004 (`mcp_protocol.py`); MCP-021, MCP-022 (`deps.py`) |
| S2 | PROTO-005, PROTO-006 (`mcp_protocol.py`); MCP-014, MCP-017 (`ci.py`); MCP-023 (`deps.py`) |
| S3 | *(default — set explicitly on none)* |
| S4 | MCP-018 (`ci.py`) |
| S0 (meta) | MCP-STAGE-DECL, MCP-STAGE-DRIFT (`stage_meta.py`) |

---

## Task 1: Stage enum + min_stage fields

**Files:**
- Modify: `consistency_check/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_types.py`:

```python
def test_stage_enum_values() -> None:
    from consistency_check.types import Stage

    assert [s.value for s in Stage] == ["S0", "S1", "S2", "S3", "S4"]


def test_rule_min_stage_defaults_to_s3() -> None:
    from consistency_check.types import Rule, Stage, Tier

    rule = Rule(id="X-001", tier=Tier.MUST, statement="x", check=lambda _r: None)
    assert rule.min_stage is Stage.S3


def test_finding_min_stage_defaults_to_s3() -> None:
    from consistency_check.types import Finding, FindingStatus, Stage, Tier

    finding = Finding(rule_id="X-001", tier=Tier.MUST, status=FindingStatus.PASS)
    assert finding.min_stage is Stage.S3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_types.py -q`
Expected: FAIL — `ImportError: cannot import name 'Stage'`.

- [ ] **Step 3: Add the enum and fields**

In `consistency_check/types.py`, add after the `FindingStatus` enum (around line 29):

```python
class Stage(StrEnum):
    """MCP server maturity stage. Completeness axis, orthogonal to Tier."""

    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
```

Add `min_stage` to `Finding` (after the `evidence` field):

```python
    min_stage: Stage = Stage.S3
```

Add `min_stage` to `Rule` (after the `applies_to` field):

```python
    min_stage: Stage = Stage.S3
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_types.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add consistency_check/types.py tests/test_types.py
git commit -m "Add Stage enum and min_stage to Rule and Finding"
```

---

## Task 2: declared_stage parser

**Files:**
- Create: `consistency_check/stage.py`
- Test: `tests/test_stage.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_stage.py`:

```python
"""Tests for stage parsing, SCOPE.md parsing, and drift signals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.stage import declared_stage, next_stage, stage_rank
from consistency_check.types import Repo, Stage

if TYPE_CHECKING:
    from pathlib import Path


def _repo(root: Path, language: str = "python") -> Repo:
    return Repo(name=root.name, path=root, language=language, github_slug="x/y")


def _write_readme(root: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(body, encoding="utf-8")


def test_declared_stage_reads_token_from_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nAlpha. Stage: S2.\n\n## License\nMIT\n")
    assert declared_stage(_repo(tmp_path)) is Stage.S2


def test_declared_stage_is_none_when_no_token(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nUnder active development.\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_is_none_without_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## License\nMIT\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_is_none_when_readme_missing(tmp_path: Path) -> None:
    assert declared_stage(_repo(tmp_path)) is None


def test_declared_stage_ignores_token_outside_status_section(tmp_path: Path) -> None:
    _write_readme(tmp_path, "# x\n\n## Status\nAlpha.\n\n## Notes\nSee S3 spec.\n")
    assert declared_stage(_repo(tmp_path)) is None


def test_stage_rank_orders_s0_below_s4() -> None:
    assert stage_rank(Stage.S0) < stage_rank(Stage.S2) < stage_rank(Stage.S4)


def test_next_stage_returns_successor_and_none_at_top() -> None:
    assert next_stage(Stage.S2) is Stage.S3
    assert next_stage(Stage.S4) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stage.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'consistency_check.stage'`.

- [ ] **Step 3: Create the module**

Create `consistency_check/stage.py`:

```python
"""Maturity-stage parsing, SCOPE.md parsing, and drift signals.

Pure and side-effect-free: every function reads repo files and returns data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from consistency_check.types import Stage

if TYPE_CHECKING:
    from consistency_check.types import Repo

_STAGE_ORDER = (Stage.S0, Stage.S1, Stage.S2, Stage.S3, Stage.S4)
_STATUS_SECTION = re.compile(r"(?ims)^##\s+status\b(.*?)(?=^##\s|\Z)")
_STAGE_TOKEN = re.compile(r"\bS([0-4])\b")


def stage_rank(stage: Stage) -> int:
    """Return the 0-based ordinal of ``stage`` (S0 -> 0 ... S4 -> 4)."""
    return _STAGE_ORDER.index(stage)


def next_stage(stage: Stage) -> Stage | None:
    """Return the stage one rung above ``stage``, or None at the top (S4)."""
    idx = _STAGE_ORDER.index(stage)
    return _STAGE_ORDER[idx + 1] if idx + 1 < len(_STAGE_ORDER) else None


def declared_stage(repo: Repo) -> Stage | None:
    """Read the repo's declared stage from the README ``## Status`` section.

    Returns the parsed Stage, or None when the README is missing, has no
    ``## Status`` section, or that section carries no S0-S4 token (unstaged).
    """
    readme = repo.path / "README.md"
    if not readme.is_file():
        return None
    section = _STATUS_SECTION.search(readme.read_text(encoding="utf-8", errors="replace"))
    if section is None:
        return None
    token = _STAGE_TOKEN.search(section.group(1))
    if token is None:
        return None
    return Stage(f"S{token.group(1)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stage.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add consistency_check/stage.py tests/test_stage.py
git commit -m "Add declared_stage parser and stage ordering helpers"
```

---

## Task 3: SCOPE.md parser

**Files:**
- Modify: `consistency_check/stage.py`
- Test: `tests/test_stage.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stage.py`:

```python
def test_surface_operations_parses_bullets(tmp_path: Path) -> None:
    from consistency_check.stage import surface_operations

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text(
        "# Scope\n\n## Surface\n- list_devices\n- create_wlan\n\n## Auth\nAPI key.\n",
        encoding="utf-8",
    )
    assert surface_operations(_repo(tmp_path)) == ["list_devices", "create_wlan"]


def test_surface_operations_empty_without_scope_file(tmp_path: Path) -> None:
    from consistency_check.stage import surface_operations

    tmp_path.mkdir(parents=True, exist_ok=True)
    assert surface_operations(_repo(tmp_path)) == []


def test_has_scope_exception_detects_heading(tmp_path: Path) -> None:
    from consistency_check.stage import has_scope_exception

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text(
        "## Surface\n- x\n\n## Scope exception\nWLAN only; rest out of scope.\n",
        encoding="utf-8",
    )
    assert has_scope_exception(_repo(tmp_path)) is True


def test_has_scope_exception_false_without_heading(tmp_path: Path) -> None:
    from consistency_check.stage import has_scope_exception

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SCOPE.md").write_text("## Surface\n- x\n", encoding="utf-8")
    assert has_scope_exception(_repo(tmp_path)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stage.py -q`
Expected: FAIL — `ImportError: cannot import name 'surface_operations'`.

- [ ] **Step 3: Add the parsers**

In `consistency_check/stage.py`, add the patterns near the top (after `_STAGE_TOKEN`):

```python
_SURFACE_SECTION = re.compile(r"(?ims)^##\s+surface\b(.*?)(?=^##\s|\Z)")
_EXCEPTION_HEADING = re.compile(r"(?im)^##\s+scope exception\b")
```

Add the functions at the end of the module:

```python
def surface_operations(repo: Repo) -> list[str]:
    """Return the declared operations from SCOPE.md ``## Surface`` (one per bullet)."""
    scope = repo.path / "SCOPE.md"
    if not scope.is_file():
        return []
    section = _SURFACE_SECTION.search(scope.read_text(encoding="utf-8", errors="replace"))
    if section is None:
        return []
    ops: list[str] = []
    for line in section.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            ops.append(stripped[1:].strip())
    return ops


def has_scope_exception(repo: Repo) -> bool:
    """Return True when SCOPE.md declares a ``## Scope exception`` heading."""
    scope = repo.path / "SCOPE.md"
    if not scope.is_file():
        return False
    return _EXCEPTION_HEADING.search(scope.read_text(encoding="utf-8", errors="replace")) is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stage.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add consistency_check/stage.py tests/test_stage.py
git commit -m "Parse SCOPE.md surface list and scope-exception heading"
```

---

## Task 4: drift signals

**Files:**
- Modify: `consistency_check/stage.py`
- Test: `tests/test_stage.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stage.py`:

```python
def test_drift_s0_with_src_tree(tmp_path: Path) -> None:
    from consistency_check.stage import drift_signal

    (tmp_path / "src").mkdir(parents=True)
    assert drift_signal(_repo(tmp_path), Stage.S0) is not None


def test_drift_s1_without_src_tree(tmp_path: Path) -> None:
    from consistency_check.stage import drift_signal

    tmp_path.mkdir(parents=True, exist_ok=True)
    assert drift_signal(_repo(tmp_path), Stage.S1) is not None


def test_drift_s2_without_ci(tmp_path: Path) -> None:
    from consistency_check.stage import drift_signal

    (tmp_path / "src").mkdir(parents=True)
    assert drift_signal(_repo(tmp_path), Stage.S2) is not None


def test_no_drift_for_staged_s2_repo(tmp_path: Path) -> None:
    from consistency_check.stage import drift_signal

    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    assert drift_signal(_repo(tmp_path), Stage.S2) is None


def test_drift_go_source_tree_accepts_cmd(tmp_path: Path) -> None:
    from consistency_check.stage import drift_signal

    (tmp_path / "cmd").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    assert drift_signal(_repo(tmp_path, language="go"), Stage.S2) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stage.py -q`
Expected: FAIL — `ImportError: cannot import name 'drift_signal'`.

- [ ] **Step 3: Add drift detection**

Append to `consistency_check/stage.py`:

```python
def _has_source_tree(repo: Repo) -> bool:
    if repo.language == "go":
        return (repo.path / "cmd").is_dir() or (repo.path / "internal").is_dir()
    return (repo.path / "src").is_dir()


def _has_ci(repo: Repo) -> bool:
    workflows = repo.path / ".github" / "workflows"
    return workflows.is_dir() and any(
        p.suffix in {".yml", ".yaml"} for p in workflows.iterdir() if p.is_file()
    )


def _has_integration_marker(repo: Repo) -> bool:
    return (repo.path / "tests" / "integration").is_dir() or (repo.path / "integration").is_dir()


def _has_release_path(repo: Repo) -> bool:
    workflows = repo.path / ".github" / "workflows"
    if workflows.is_dir() and any("release" in p.name.lower() for p in workflows.iterdir()):
        return True
    return (repo.path / "mcpb").exists()


def drift_signal(repo: Repo, declared: Stage) -> str | None:
    """Return a one-line drift description when cheap signals contradict ``declared``.

    Coarse static checks only; catches obvious contradictions, not a full re-audit.
    """
    has_src = _has_source_tree(repo)
    if declared is Stage.S0 and has_src:
        return "declared S0 but a source tree exists"
    if stage_rank(declared) >= stage_rank(Stage.S1) and not has_src:
        return "declared S1+ but no source tree found"
    if stage_rank(declared) >= stage_rank(Stage.S2) and not _has_ci(repo):
        return "declared S2+ but no CI workflow present"
    if stage_rank(declared) >= stage_rank(Stage.S3) and not _has_integration_marker(repo):
        return "declared S3+ but no integration-test directory found"
    if declared is Stage.S4 and not _has_release_path(repo):
        return "declared S4 but no release pipeline or deployment manifest found"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_stage.py -q`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add consistency_check/stage.py tests/test_stage.py
git commit -m "Add coarse per-stage drift signals"
```

---

## Task 5: stages.md doctrine doc (ladder + min_stage map)

**Files:**
- Create: `docs/standards/stages.md`

This doc is the rubric source of truth. It is authored before the meta-rules so the meta-test (Task 7) has headings to find. Do **not** add the `### MCP-STAGE-*` headings yet — those land in Task 6 alongside the implemented rules, to keep the docs↔code meta-test green at every commit.

- [ ] **Step 1: Write the doc**

Create `docs/standards/stages.md`:

```markdown
# MCP Server Maturity Stages (`S0`–`S4`)

The **stage** axis records how complete an MCP server is. It is orthogonal to the
RFC-2119 **tier** axis (MUST/SHOULD/MAY) and to the **release** axis (semver `vN`).
A repo declares its stage with an `S0`–`S4` token in its README `## Status`
section; the auditor evaluates only rules whose `min_stage` is at or below the
declared stage and reports the next stage's rules as a promotion checklist.

See `docs/superpowers/specs/2026-06-01-mcp-maturity-ladder-design.md` for the
full design rationale.

## The ladder

- **S0 Documented** — docs-first repo, no `src/`. README, SCOPE.md, endpoint map,
  curl recipes, and at least one ordered runbook. Teaches an agent to drive the
  API by hand.
- **S1 Walking skeleton** — server runs; read-only tools; stdio; unit tests on
  cassettes.
- **S2 Wrapped** — read and write tools; writes env-gated default-off; CI green;
  lockfile committed.
- **S3 Complete** — full surface parity with the declared scope; live integration
  tests; runbooks promoted to MCP prompts; SHOULDs satisfied.
- **S4 Distributed** — deployment model wired plus a release pipeline and
  versioned releases.

## min_stage map

Closure rule: any rule not listed here defaults to `min_stage = S3`;
deployment/release rules are `S4`.

| min_stage | Rules |
|---|---|
| S0 | MCP-001, MCP-002, MCP-005, MCP-006, MCP-007, MCP-009, MCP-010, MCP-019, MCP-020 |
| S1 | PROTO-001, PROTO-002, PROTO-003, PROTO-004, MCP-021, MCP-022 |
| S2 | PROTO-005, PROTO-006, MCP-014, MCP-017, MCP-023 |
| S3 | *(all rules not otherwise listed)* |
| S4 | MCP-018 |

## SCOPE.md format

`SCOPE.md` is written at S0 and parsed by the auditor:

- `## Surface` — one declared operation per bullet; the S3 coverage check measures
  wrapped tools against this list.
- `## Auth` — the auth model, in prose.
- `## Scope exception` *(optional)* — present only for a deliberate
  scoped-complete stop. Its presence holds the repo to its declared subset rather
  than the full surface.

## Stage declaration

A repo declares its stage inside the `## Status` section already required by
MCP-007 (e.g. a line `Stage: S2`). The accepted token set is `S0`–`S4`. A repo
whose `## Status` section carries no `S`-token is **unstaged**: the auditor runs
every rule (no stage filtering) and emits the MCP-STAGE-DECL warning.
```

- [ ] **Step 2: Verify the meta-test still passes (no new headings yet)**

Run: `uv run pytest tests/test_meta.py -q`
Expected: PASS — `stages.md` is not yet scanned and adds no `### XXX-000` headings.

- [ ] **Step 3: Commit**

```bash
git add docs/standards/stages.md
git commit -m "Document the S0-S4 maturity ladder and min_stage map"
```

---

## Task 6: stage meta-rules (MCP-STAGE-DECL, MCP-STAGE-DRIFT)

**Files:**
- Create: `consistency_check/rules/stage_meta.py`
- Modify: `consistency_check/audit.py` (register the module)
- Modify: `docs/standards/stages.md` (add the two `###` headings)
- Modify: `tests/test_meta.py` (scan `stages.md`; accept `MCP-STAGE-*`)
- Modify: `tests/fixtures/build.py` (declare a stage in good fixtures)
- Modify: `tests/test_sweep.py` (exempt MCP-STAGE-DRIFT on bad fixtures)
- Test: `tests/rules/test_stage_meta.py`

These changes land together so the docs↔code invariant and the sweep contract stay green in one commit.

- [ ] **Step 1: Write the failing test**

Create `tests/rules/test_stage_meta.py`:

```python
"""Tests for the stage meta-rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.rules.stage_meta import RULES
from consistency_check.types import Repo

if TYPE_CHECKING:
    from pathlib import Path

_BY_ID = {r.id: r for r in RULES}


def _repo(root: Path) -> Repo:
    return Repo(name=root.name, path=root, language="python", github_slug="x/y")


def test_decl_fails_when_unstaged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nAlpha.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DECL"].check(_repo(tmp_path)) is not None


def test_decl_passes_when_staged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S1.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DECL"].check(_repo(tmp_path)) is None


def test_drift_passes_when_unstaged(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nAlpha.\n", encoding="utf-8")
    assert _BY_ID["MCP-STAGE-DRIFT"].check(_repo(tmp_path)) is None


def test_drift_fires_on_s0_with_src(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n## Status\nStage: S0.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    assert _BY_ID["MCP-STAGE-DRIFT"].check(_repo(tmp_path)) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rules/test_stage_meta.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'consistency_check.rules.stage_meta'`.

- [ ] **Step 3: Create the meta-rules module**

Create `consistency_check/rules/stage_meta.py`:

```python
"""Meta-rules: stage declaration and stage drift (MAY-tier, never block exit 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency_check.stage import declared_stage, drift_signal
from consistency_check.types import Rule, Stage, Tier

if TYPE_CHECKING:
    from consistency_check.types import Repo


def _check_stage_declared(repo: Repo) -> str | None:
    if declared_stage(repo) is None:
        return "README ## Status section declares no S0-S4 stage token (unstaged)"
    return None


def _check_stage_drift(repo: Repo) -> str | None:
    declared = declared_stage(repo)
    if declared is None:
        return None
    return drift_signal(repo, declared)


RULES: tuple[Rule, ...] = (
    Rule(
        id="MCP-STAGE-DECL",
        tier=Tier.MAY,
        statement="README ## Status declares a maturity stage (S0-S4)",
        check=_check_stage_declared,
        min_stage=Stage.S0,
    ),
    Rule(
        id="MCP-STAGE-DRIFT",
        tier=Tier.MAY,
        statement="Declared stage matches the repo's cheap structural signals",
        check=_check_stage_drift,
        min_stage=Stage.S0,
    ),
)
```

- [ ] **Step 4: Register the module**

In `consistency_check/audit.py`, add to `_RULE_MODULES` (after `"consistency_check.rules.go",`):

```python
    "consistency_check.rules.stage_meta",
```

- [ ] **Step 5: Add the doc headings**

Append to `docs/standards/stages.md`:

```markdown
## Meta-rules

### MCP-STAGE-DECL — README declares a maturity stage [MAY]

Fires when the `## Status` section carries no `S0`-`S4` token. MAY-tier, so it
surfaces in the report without setting a nonzero exit code.

### MCP-STAGE-DRIFT — declared stage matches repo signals [MAY]

Fires when the declared stage contradicts the cheap structural signals (e.g. an
`S0` repo with a `src/` tree, or an `S2`+ repo with no CI). MAY-tier.
```

- [ ] **Step 6: Update the meta-test to scan stages.md and accept STAGE ids**

In `tests/test_meta.py`, replace the `_RULE_HEADING` regex (line 12):

```python
_RULE_HEADING = re.compile(r"(?m)^###\s+([A-Z]+-(?:\d{3}|STAGE-[A-Z]+))\b")
```

and add `"stages.md"` to the file tuple in `_documented_ids()`:

```python
    for f in ("mcp.md", "python.md", "go.md", "mcp-protocol.md", "stages.md"):
```

- [ ] **Step 7: Declare a stage in the good fixtures**

In `tests/fixtures/build.py`, change the good-Python README `## Status` body (line ~27) from `Alpha.` to:

```
        ## Status
        Alpha. Stage: S2.
```

and the good-Go README `## Status` body (line ~248) from `Alpha.` to:

```
        ## Status
        Alpha. Stage: S2.
```

(The good fixtures have a source tree and a `ci.yml`, so `S2` produces no drift. Leave the bad fixtures unstaged.)

- [ ] **Step 8: Exempt MCP-STAGE-DRIFT on the unstaged bad fixtures**

In `tests/test_sweep.py`, add `"MCP-STAGE-DRIFT"` to both entries of `_CANNOT_FAIL` and document why:

```python
#   MCP-STAGE-DRIFT cannot fire on the bad fixtures: they are unstaged, so the
#                   drift check returns None (it only compares against a declared
#                   stage). MCP-STAGE-DECL still fails them.
_CANNOT_FAIL: dict[str, frozenset[str]] = {
    "python": frozenset({"MCP-024", "PROTO-008", "PY-003", "MCP-STAGE-DRIFT"}),
    "go": frozenset({"MCP-024", "PROTO-003", "PROTO-004", "PROTO-015", "MCP-STAGE-DRIFT"}),
}
```

- [ ] **Step 9: Run the affected suites**

Run: `uv run pytest tests/rules/test_stage_meta.py tests/test_meta.py tests/test_sweep.py -q`
Expected: PASS. The meta-test sees `MCP-STAGE-DECL`/`MCP-STAGE-DRIFT` documented in `stages.md` and implemented in `stage_meta.py` (sets match). The good fixtures pass both meta-rules; the bad fixtures fail MCP-STAGE-DECL and exempt MCP-STAGE-DRIFT.

- [ ] **Step 10: Commit**

```bash
git add consistency_check/rules/stage_meta.py consistency_check/audit.py \
        docs/standards/stages.md tests/test_meta.py tests/fixtures/build.py \
        tests/test_sweep.py tests/rules/test_stage_meta.py
git commit -m "Add stage declaration and drift meta-rules"
```

---

## Task 7: assign min_stage to ladder rules

**Files:**
- Modify: `consistency_check/rules/structure.py`, `docs.py`, `security.py`, `ci.py`, `deps.py`, `mcp_protocol.py`
- Test: `tests/test_min_stage_map.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_min_stage_map.py`:

```python
"""Pin the min_stage assignment so it matches docs/standards/stages.md."""

from __future__ import annotations

from consistency_check.audit import all_rules
from consistency_check.types import Stage

_EXPECTED: dict[str, Stage] = {
    "MCP-001": Stage.S0, "MCP-002": Stage.S0, "MCP-005": Stage.S0, "MCP-006": Stage.S0,
    "MCP-007": Stage.S0, "MCP-009": Stage.S0, "MCP-010": Stage.S0,
    "MCP-019": Stage.S0, "MCP-020": Stage.S0,
    "PROTO-001": Stage.S1, "PROTO-002": Stage.S1, "PROTO-003": Stage.S1, "PROTO-004": Stage.S1,
    "MCP-021": Stage.S1, "MCP-022": Stage.S1,
    "PROTO-005": Stage.S2, "PROTO-006": Stage.S2,
    "MCP-014": Stage.S2, "MCP-017": Stage.S2, "MCP-023": Stage.S2,
    "MCP-018": Stage.S4,
    "MCP-STAGE-DECL": Stage.S0, "MCP-STAGE-DRIFT": Stage.S0,
}


def test_min_stage_assignments_match_doc() -> None:
    by_id = {r.id: r for r in all_rules()}
    mismatches = {
        rid: (by_id[rid].min_stage, expected)
        for rid, expected in _EXPECTED.items()
        if by_id[rid].min_stage is not expected
    }
    assert not mismatches, f"min_stage mismatches (actual, expected): {mismatches}"


def test_unlisted_rules_default_to_s3() -> None:
    explicit = set(_EXPECTED)
    for rule in all_rules():
        if rule.id not in explicit:
            assert rule.min_stage is Stage.S3, f"{rule.id} should default to S3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_min_stage_map.py -q`
Expected: FAIL — S0/S1/S2/S4 rules currently default to S3.

- [ ] **Step 3: Set min_stage on each ladder rule**

Add `min_stage=Stage.SX` to the listed `Rule(...)` constructors and import `Stage` in each module (the modules currently import `from consistency_check.types import Rule, Tier` — extend to `Rule, Stage, Tier`).

- `structure.py`: `Stage.S0` on MCP-001, MCP-002, MCP-005, MCP-006.
- `docs.py`: `Stage.S0` on MCP-007, MCP-009, MCP-010. (Leave MCP-003, MCP-004, MCP-008 at default.)
- `security.py`: `Stage.S0` on MCP-019, MCP-020.
- `ci.py`: `Stage.S2` on MCP-014, MCP-017; `Stage.S4` on MCP-018. (Leave MCP-015, MCP-016, MCP-025, MCP-026 at default.)
- `deps.py`: `Stage.S1` on MCP-021, MCP-022; `Stage.S2` on MCP-023. (Leave MCP-024 at default.)
- `mcp_protocol.py`: `Stage.S1` on PROTO-001, PROTO-002, PROTO-003, PROTO-004; `Stage.S2` on PROTO-005, PROTO-006. (Leave PROTO-007..017 at default.)

Example (`structure.py` MCP-001):

```python
    Rule(
        id="MCP-001",
        tier=Tier.MUST,
        statement="Top-level files: README.md, LICENSE, CLAUDE.md, SECURITY.md",
        check=_check_required_files,
        min_stage=Stage.S0,
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_min_stage_map.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add consistency_check/rules/*.py tests/test_min_stage_map.py
git commit -m "Assign min_stage to the ladder rules per stages.md"
```

---

## Task 8: stage-filter the audit driver

**Files:**
- Modify: `consistency_check/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit.py`:

```python
def test_above_stage_rules_recorded_na(tmp_path: Path) -> None:
    from consistency_check.stage import stage_rank
    from consistency_check.types import Stage

    root = tmp_path / "staged"
    root.mkdir()
    # Minimal repo declared S0: only S0 rules should be evaluated; higher ones NA.
    (root / "README.md").write_text("# x\n\n## Status\nStage: S0.\n", encoding="utf-8")
    repo = Repo(name="staged", path=root, language="python", github_slug="x/y")

    findings = audit_repo(repo)
    by_id = {f.rule_id: f for f in findings}
    # A MUST rule above S0 (e.g. MCP-014 at S2) must be skipped as n/a.
    assert by_id["MCP-014"].status == FindingStatus.NA
    assert stage_rank(by_id["MCP-014"].min_stage) > stage_rank(Stage.S0)


def test_unstaged_repo_runs_all_rules(good_python_repo: Path, monkeypatch) -> None:
    import consistency_check.audit as audit_mod

    # Force unstaged regardless of fixture README.
    monkeypatch.setattr(audit_mod, "declared_stage", lambda _r: None)
    repo = Repo(name="good", path=good_python_repo, language="python", github_slug="x/y")
    findings = audit_repo(repo)
    # No finding is skipped for being above-stage when unstaged.
    above = [f for f in findings if f.status == FindingStatus.NA and f.evidence.startswith("min_stage")]
    assert not above
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit.py -q`
Expected: FAIL — `MCP-014` is currently evaluated (FAIL/PASS), not NA; and `declared_stage` is not yet imported in `audit.py`.

- [ ] **Step 3: Add stage filtering**

In `consistency_check/audit.py`, add the import (after the existing `from consistency_check.types import ...`):

```python
from consistency_check.stage import declared_stage, stage_rank
```

Replace the body of the `for rule in all_rules():` loop in `audit_repo` so it stamps `min_stage` on every finding and skips above-stage rules:

```python
    declared = declared_stage(repo)
    findings: list[Finding] = []
    for rule in all_rules():
        if repo.language not in rule.applies_to:
            findings.append(
                Finding(rule_id=rule.id, tier=rule.tier, status=FindingStatus.NA, min_stage=rule.min_stage)
            )
            continue
        if declared is not None and stage_rank(rule.min_stage) > stage_rank(declared):
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.NA,
                    evidence=f"min_stage {rule.min_stage.value} above declared {declared.value}",
                    min_stage=rule.min_stage,
                )
            )
            continue
        try:
            evidence = rule.check(repo)
        except Exception as exc:  # noqa: BLE001 — isolation by design
            findings.append(
                Finding(
                    rule_id=rule.id,
                    tier=rule.tier,
                    status=FindingStatus.ERROR,
                    evidence=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}",
                    min_stage=rule.min_stage,
                )
            )
            continue
        status = FindingStatus.PASS if evidence is None else FindingStatus.FAIL
        findings.append(
            Finding(
                rule_id=rule.id,
                tier=rule.tier,
                status=status,
                evidence="" if evidence is None else evidence,
                min_stage=rule.min_stage,
            )
        )
    return findings
```

Remove the now-duplicated `findings: list[Finding] = []` line that preceded the loop.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audit.py -q`
Expected: PASS. Then `uv run pytest tests/test_sweep.py -q` — still PASS (the sweep calls `rule.check` directly and is unaffected by driver-level filtering).

- [ ] **Step 5: Commit**

```bash
git add consistency_check/audit.py tests/test_audit.py
git commit -m "Skip above-stage rules in the audit driver"
```

---

## Task 9: render the Stage section in the report

**Files:**
- Modify: `consistency_check/report.py`
- Modify: `consistency_check/__main__.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_report.py`, add `Stage` to the import and add a staged finding set + tests:

```python
from consistency_check.types import Finding, FindingStatus, Stage, Tier
```

```python
def _staged_findings() -> list[Finding]:
    return [
        Finding(rule_id="MCP-001", tier=Tier.MUST, status=FindingStatus.PASS, min_stage=Stage.S0),
        Finding(rule_id="MCP-014", tier=Tier.MUST, status=FindingStatus.NA,
                evidence="min_stage S2 above declared S1", min_stage=Stage.S2),
        Finding(rule_id="PROTO-001", tier=Tier.MUST, status=FindingStatus.FAIL,
                evidence="tool not snake_case", min_stage=Stage.S1),
    ]


def test_umbrella_unstaged_section(snapshot) -> None:
    body = render_umbrella(repo_name="u", findings=_findings(), declared_stage=None)
    assert "## Stage" in body
    assert "Unstaged" in body


def test_umbrella_staged_section(snapshot) -> None:
    body = render_umbrella(repo_name="s", findings=_staged_findings(), declared_stage=Stage.S1)
    assert body == snapshot
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report.py -q`
Expected: FAIL — `render_umbrella() got an unexpected keyword argument 'declared_stage'`.

- [ ] **Step 3: Add the Stage section**

In `consistency_check/report.py`, add imports:

```python
from consistency_check.stage import next_stage, stage_rank
from consistency_check.types import Finding, FindingStatus, Stage, Tier
```

Change the `render_umbrella` signature:

```python
def render_umbrella(
    repo_name: str, findings: list[Finding], *, declared_stage: Stage | None = None
) -> str:
```

Insert the stage section into the `lines` list right after the summary block (after the `summary,` / `"",` entries, before the `if must_fails or should_fails:` block):

```python
    lines += _stage_section(findings, declared_stage)
```

Add the helper at the end of the module:

```python
def _stage_section(findings: list[Finding], declared: Stage | None) -> list[str]:
    out = ["## Stage", ""]
    if declared is None:
        out += [
            "Unstaged — add an `S0`-`S4` token to the README `## Status` section.",
            "",
        ]
        return out
    at_or_below = [f for f in findings if stage_rank(f.min_stage) <= stage_rank(declared)]
    gate_fails = [f for f in at_or_below if f.tier == Tier.MUST and f.status == FindingStatus.FAIL]
    if gate_fails:
        ids = ", ".join(f.rule_id for f in gate_fails)
        out.append(f"Declared **{declared.value}**; {declared.value} gates failing: {ids}.")
    else:
        out.append(f"Declared **{declared.value}**; compliant through {declared.value} gates.")
    nxt = next_stage(declared)
    if nxt is not None:
        pending = sorted(
            {
                f.rule_id
                for f in findings
                if f.min_stage is nxt and f.status in (FindingStatus.FAIL, FindingStatus.NA)
            }
        )
        if pending:
            out += ["", f"To reach **{nxt.value}**: {', '.join(pending)}."]
    out.append("")
    return out
```

- [ ] **Step 4: Thread declared_stage from both render_umbrella callers**

There are two callers (`rg -n "render_umbrella(" consistency_check`): `__main__.py` (stdout/`--out`) and `filer.py` (the `--apply` GitHub path). Both must pass the stage or filed issues show "Unstaged" for staged repos.

In `consistency_check/__main__.py`, add the import:

```python
from consistency_check.stage import declared_stage
```

and update the `render_umbrella` call (line ~47):

```python
        body = render_umbrella(repo.name, findings, declared_stage=declared_stage(repo))
```

In `consistency_check/filer.py`, add the same import and update the call (line ~51, inside `file_repo_findings(repo, findings, ...)` — `repo` is in scope):

```python
    umbrella_body = render_umbrella(repo.name, findings, declared_stage=declared_stage(repo))
```

- [ ] **Step 5: Regenerate the snapshot and run**

Run: `uv run pytest tests/test_report.py -q --snapshot-update`
Then: `uv run pytest tests/test_report.py -q`
Expected: PASS. Inspect the snapshot diff: the existing umbrella snapshot now carries a `## Stage` / `Unstaged` block, and the new staged snapshot shows "compliant through S1 gates" is **not** emitted (PROTO-001 at S1 fails, so it reads "S1 gates failing: PROTO-001" and "To reach S2: MCP-014").

- [ ] **Step 6: Commit**

```bash
git add consistency_check/report.py consistency_check/__main__.py consistency_check/filer.py \
        tests/test_report.py tests/__snapshots__/
git commit -m "Render maturity-stage section in the audit report"
```

---

## Task 10: full consistency-check verification

**Files:** none (verification only)

- [ ] **Step 1: Lint, format, types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run ty check`
Expected: clean. Fix any finding before proceeding (zero-warnings policy).

- [ ] **Step 2: Full test suite**

Run: `uv run pytest -q`
Expected: all pass, including `test_meta.py`, `test_sweep.py`, `test_audit.py`, `test_report.py`, `test_stage.py`, `test_stage_meta.py`, `test_min_stage_map.py`.

- [ ] **Step 3: Smoke-run the auditor against a real repo**

Run: `uv run consistency-check audit --repo unifi-mcp`
Expected: exit 0 or 1 (not 2/3); the report contains a `## Stage` section reading "Unstaged" (unifi-mcp's README has no S-token yet); MCP-STAGE-DECL appears under Suggestions (MAY), and exit code is unchanged by that MAY finding.

- [ ] **Step 4: Commit (only if Step 1 required fixes)**

```bash
git add -A
git commit -m "Fix lint/type findings from maturity-ladder work"
```

---

## Task 11: workspace doctrine pointer

**Files:**
- Modify: `~/Projects/mcp-server-dev-defaults/CLAUDE.md` (symlink target of the workspace `CLAUDE.md`)

- [ ] **Step 1: Add the doctrine section**

Append a section to `~/Projects/mcp-server-dev-defaults/CLAUDE.md` under the "Canonical standards" area:

```markdown
## Maturity stages (S0–S4)

Every server has a **stage** (how complete) independent of its **tier** compliance
(how correct) and **release** version (what's shipped). New integrations start at
**S0** (docs-first: SCOPE.md + curl runbooks, no `src/`) and climb to **S4**
(distributed). Declare the stage with an `S0`–`S4` token in the README `## Status`
section; the auditor scopes rules to the declared stage and reports the next
stage's gate.

Full ladder and per-rule `min_stage` map:
`~/Projects/consistency-check/docs/standards/stages.md`.
```

- [ ] **Step 2: Verify the symlink reflects it**

Run: `grep -c "Maturity stages" ~/Projects/mcp-server-dev/CLAUDE.md`
Expected: `1` (the workspace CLAUDE.md is a symlink to the file just edited).

- [ ] **Step 3: Commit (in the defaults repo if it is one)**

```bash
cd ~/Projects/mcp-server-dev-defaults && git add CLAUDE.md && \
  git commit -m "Document the S0-S4 maturity ladder for the workspace" || \
  echo "not a git repo or nothing to commit — skip"
```

---

## Task 12: build-mcp-server S0 on-ramp

**Files:**
- Modify: `build-mcp-server` `SKILL.md`

> **CAVEAT — confirm the source location first.** The only copy found is the plugin cache at
> `~/.claude/plugins/cache/claude-plugins-official/mcp-server-dev/unknown/skills/build-mcp-server/SKILL.md`.
> Edits there may be overwritten on plugin update. Before editing, check for a editable plugin source
> (e.g. a `claude-defaults`/plugins repo). If only the cache exists, make the edit there and note in the
> commit message that it must be upstreamed. **Do not proceed silently if no durable source exists — ask.**

- [ ] **Step 1: Insert Phase 0 before Phase 1**

In `SKILL.md`, add a new section immediately before `## Phase 1 — Interrogate the use case`:

```markdown
## Phase 0 — Scaffold at S0 (docs-first)

Before any deployment-model or tool questions, stand the repo up at **stage S0**:
docs only, no `src/`. This is the sanctioned on-ramp (see
`consistency-check/docs/standards/stages.md`).

Create: `README.md` (with `## Status` declaring `Stage: S0`), `SCOPE.md`
(`## Surface` listing the target operations, `## Auth` for the auth model),
an endpoint/command map, curl recipes, and at least one ordered runbook
(commands in execution order for one real task). The repo is "done" at S0 when an
agent can complete every runbook by hand using only the repo.

Deployment model (Phase 2 below) and tool patterns (Phase 3) are decided later,
on the climb from S3 to S4 — not now.
```

- [ ] **Step 2: Cross-reference from the deployment-model phase**

At the top of `## Phase 2 — Recommend a deployment model`, add:

```markdown
> This is the **S3→S4** decision. Don't pick a deployment model before tools exist.
```

- [ ] **Step 3: Verify**

Run: `grep -n "Phase 0 — Scaffold at S0" <path-to-SKILL.md>`
Expected: one match, located before the Phase 1 heading.

- [ ] **Step 4: Commit (if the source is a git repo)**

```bash
git add <path-to-SKILL.md> && git commit -m "Add S0 docs-first Phase 0 to build-mcp-server" || \
  echo "plugin cache is not a tracked repo — record the change for upstreaming"
```

---

## Self-review notes (already reconciled in this plan)

- **Spec coverage:** three orthogonal axes (Task 1 `Stage`), the S0–S4 ladder + `min_stage` (Tasks 5, 7), stage declaration via README `## Status` (Task 2), SCOPE.md format (Task 3), drift signals / risk table (Task 4), MCP-STAGE-DECL/DRIFT as MAY findings reusing the Finding model (Task 6), stage-aware evaluation + next-gate reporting (Tasks 8, 9), doctrine + on-ramp (Tasks 11, 12).
- **Deferred (named, not silently dropped):** the **quantitative S3 coverage check** (count wrapped tools vs `## Surface` bullets) is *not* implemented here. `surface_operations()` (Task 3) provides the parser, but cross-language tool-counting is a project of its own and no current repo declares a stage, so the coverage comparison is left as a follow-up. The S3 drift signal (integration-test presence) is the coarse stand-in. Flag this to the user.
- **Naming reconciliation:** the spec's `MCP-STAGE-DECL`/`MCP-STAGE-DRIFT` names are kept verbatim by extending the meta-test heading regex (Task 6), rather than renumbering them as `MCP-027/028`.
- **Backward compatibility:** all six current repos parse as unstaged → no rules filtered, one new MAY finding each (MCP-STAGE-DECL), exit codes unchanged.
```
