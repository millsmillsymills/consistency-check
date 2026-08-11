# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A rule-based audit tool that checks the millsmillsymills MCP-server suite against canonical standards. It walks each target repo, runs mechanical checks, emits markdown gap reports, and optionally files GitHub issues. The standards themselves (`docs/standards/`) are the authoritative source of truth; the code mechanically enforces them.

## Commands

```bash
uv sync --all-groups                          # install deps incl. dev group
uv run consistency-check audit                # audit all repos, print to stdout
uv run consistency-check audit --repo unifi-mcp --out reports/   # one repo → file
uv run consistency-check audit --repo unifi-mcp --apply          # file GitHub issues (idempotent)

uv run pytest -q                              # all tests
uv run pytest tests/rules/test_python.py -q   # one module
uv run pytest -q -k py_015                     # single rule by id pattern
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

Exit codes: `0` pass, or only SHOULD/MAY failures, `1` ≥1 MUST failure, `2` unknown `--repo`, a check raised, or a MUST rule went ungraded, `3` `gh` filer error under `--apply`.

## Architecture

The whole tool is a registry of pure check functions plus a driver. Data model in `consistency_check/types.py`:

- **`Rule`** — `id`, `tier` (`MUST`/`SHOULD`/`MAY`), `statement`, `check`, plus three scope fields: `applies_to` (frozenset of languages), `min_stage` (default `S3`), and `applies_to_archetype` (`None` means every archetype). The `check` is a `Callable[[Repo], str | None | NotApplicable]`: return `None` on pass, an evidence string on fail, or a `NotApplicable` when the check cannot grade the repo at all. Checks must be pure and side-effect-free.
- **`Repo`** — a target: `name`, `path`, `language`, `github_slug`.
- **`Stage`** / **`Archetype`** — two scope axes orthogonal to `Tier`: completeness (`S0`–`S4`, `docs/standards/stages.md`) and locality (`remote-hostable`/`site-local`/`host-local`, `docs/standards/deployment.md`). Both are declared in the target repo's README and read by `stage.declared_stage` / `deployment.declared_archetype`. A rule above the declared stage, or outside the declared archetype, is recorded `n/a` instead of run.
- **`Finding`** — one rule's outcome for one repo: `rule_id`, `tier`, `status` (`pass`/`fail`/`n/a`/`error`), `evidence`, `min_stage`, `applicable` (`False` only for a permanent language mismatch), `unevaluated`, `unmechanized`.
- **`NotApplicable`** — `reason`, plus `unmechanized`. Reach for it when a check cannot answer; reach for `Rule.applies_to` when the rule does not apply to the repo's language. `unmechanized=True` means no checker exists, so re-running never clears it: it is reported but does not escalate the exit code or sit on a stage-promotion checklist. The default means the audit could not run the check this time, which escalates a MUST to exit 2.

Flow: `__main__.py` → `audit.audit_repo` → `report.render_umbrella` → (optionally) `filer.file_repo_findings`.

- **`audit.py`** discovers rules by importing each module in `_RULE_MODULES` and reading its `RULES` tuple. For each rule it applies three scope gates (language, `min_stage` vs. the declared stage, archetype), records a skip as `n/a`, and wraps every `check` call so an exception becomes an `error` Finding rather than crashing the run.
- **`repos.py`** is the hardcoded `REGISTRY` of audited repos (paths under `~/Desktop/Projects/mcp-server-dev`).
- **`filer.py`** wraps the `gh` CLI. Idempotent: it upserts issues by exact title (umbrella per repo + one child per MUST/SHOULD failure), edits the umbrella in place, refuses to touch when multiple open issues match a title. Dry-run unless `--apply`.
- **`report.py`** renders umbrella and child-issue markdown. Titles here (`umbrella_issue_title`, `child_issue_title`) are the idempotency keys the filer relies on — don't change their format casually.
- **`stage.py`** / **`deployment.py`** — parse the declared stage and archetype out of the target README's `## Status` section, and compute the drift signals behind the `*-DRIFT` meta-rules.
- **`sources.py`** — source-text accessors that scrub before a check reads them. `combined_code_only_text` drops comments *and* string literals, for checks whose subject is written in code; `combined_code_text` drops comments and docstrings but keeps literals, for checks whose subject *is* a literal (a `transport="streamable-http"` argument). A check that greps source must go through one of them: matching raw text is how a marker inside a Go raw string or a Python docstring gets counted as real code.
- **`_git.py`** — `tracked_files()` helper for checks that need to know what git tracks.

### Rule ID ↔ module ↔ docs mapping

Rule IDs are referenced verbatim in three places that must stay in sync:

| Prefix     | Rule module                    | Standards doc            |
| ---------- | ------------------------------ | ------------------------ |
| `MCP-*`    | `structure`/`docs`/`tests`/`ci`/`security`/`deps` | `docs/standards/mcp.md` |
| `PY-*`     | `rules/python.py`              | `docs/standards/python.md` |
| `GO-*`     | `rules/go.py`                  | `docs/standards/go.md`     |
| `PROTO-*`  | `rules/mcp_protocol.py`        | `docs/standards/mcp-protocol.md` |
| `MCP-STAGE-*` | `rules/stage_meta.py`       | `docs/standards/stages.md` |
| `MCP-DEPLOY-*` | `rules/deployment.py`      | `docs/standards/deployment.md` |

`MCP-NNN` rules are language-agnostic and split across six modules by concern, not by prefix; the `MCP-STAGE-*` and `MCP-DEPLOY-*` meta-rules live in two more.

### Adding or changing a rule

1. Add/edit the `### XXX-000` section in the matching `docs/standards/*.md`. The heading regex in `test_meta.py` accepts a 3-digit id or a `MCP-STAGE-*`/`MCP-DEPLOY-*` meta-rule name, nothing else.
2. Add/edit the `Rule(...)` in the matching `rules/*.py` module's `RULES` tuple, same id verbatim.
3. Set `min_stage` (and `applies_to_archetype`, for deploy rules) to match the map in the standards doc; `tests/test_min_stage_map.py` pins the implementation to its own copy of that map, so a docs-only edit will not be caught — change all three.
4. If you add a new rule module, register it in `audit._RULE_MODULES`.
5. `tests/test_meta.py` enforces that documented and implemented id sets are identical — run it.

## Testing

Rule tests in `tests/rules/` exercise each module against synthetic good/bad fixture repos, one pair per language, built by `tests/fixtures/build.py` and exposed via `tests/conftest.py`: a `good_*` repo that passes every applicable rule and a `bad_*` repo that fails every one it can. `tests/test_sweep.py` enforces that contract: the good side in full, the bad side minus the handful of rules that pass in isolation no matter the input, which are exempted in its `_CANNOT_FAIL` with the reason inline. When you add a rule, extend both builders for the relevant language so the good repo still passes and the bad repo triggers the new failure — or, if the rule cannot fail on any fixture, add it to `_CANNOT_FAIL`. `test_report.py` uses syrupy snapshots (`--snapshot-update` to regenerate). Property tests for the filer use hypothesis.

Evidence is filed as issues on this public repo about private target repos, so it names a thing (a rule subject, a bare filename, a marker) and never carries a captured source span or an absolute path. `test_evidence_contract.py` holds every failing rule to a 400-character single-line bound, against the `bad_*` fixtures, so a matcher that starts capturing source is caught where it is introduced. `test_evidence_bounds.py` covers the sharper case: where the offending value is itself the secret (a tool name holding a password or internal hostname), evidence publishes where it was declared, not the value.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `millsmillsymills/consistency-check`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles using their default strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
