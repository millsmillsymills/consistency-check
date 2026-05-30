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

Exit codes: `0` pass (or only MAY), `1` ≥1 MUST failure, `2` unknown `--repo` or a check raised, `3` `gh` filer error under `--apply`.

## Architecture

The whole tool is a registry of pure check functions plus a driver. Data model in `consistency_check/types.py`:

- **`Rule`** — `id`, `tier` (`MUST`/`SHOULD`/`MAY`), `statement`, `check`, `applies_to` (frozenset of languages). The `check` is a `Callable[[Repo], str | None]`: return `None` on pass, or an evidence string on fail. Checks must be pure and side-effect-free.
- **`Repo`** — a target: `name`, `path`, `language`, `github_slug`.
- **`Finding`** — one rule's outcome for one repo: `rule_id`, `tier`, `status` (`pass`/`fail`/`n/a`/`error`), `evidence`.

Flow: `__main__.py` → `audit.audit_repo` → `report.render_umbrella` → (optionally) `filer.file_repo_findings`.

- **`audit.py`** discovers rules by importing each module in `_RULE_MODULES` and reading its `RULES` tuple. For each rule it skips repos whose `language` isn't in `applies_to` (recorded as `n/a`), and wraps every `check` call so an exception becomes an `error` Finding rather than crashing the run.
- **`repos.py`** is the hardcoded `REGISTRY` of audited repos (paths under `~/Desktop/Projects`).
- **`filer.py`** wraps the `gh` CLI. Idempotent: it upserts issues by exact title (umbrella per repo + one child per MUST/SHOULD failure), edits the umbrella in place, refuses to touch when multiple open issues match a title. Dry-run unless `--apply`.
- **`report.py`** renders umbrella and child-issue markdown. Titles here (`umbrella_issue_title`, `child_issue_title`) are the idempotency keys the filer relies on — don't change their format casually.
- **`_git.py`** — `tracked_files()` helper for checks that need to know what git tracks.

### Rule ID ↔ module ↔ docs mapping

Rule IDs are referenced verbatim in three places that must stay in sync:

| Prefix     | Rule module                    | Standards doc            |
| ---------- | ------------------------------ | ------------------------ |
| `MCP-*`    | `structure`/`docs`/`tests`/`ci`/`security`/`deps` | `docs/standards/mcp.md` |
| `PY-*`     | `rules/python.py`              | `docs/standards/python.md` |
| `GO-*`     | `rules/go.py`                  | `docs/standards/go.md`     |
| `PROTO-*`  | `rules/mcp_protocol.py`        | `docs/standards/mcp-protocol.md` |

`MCP-*` rules are language-agnostic and split across six modules by concern, not by prefix.

### Adding or changing a rule

1. Add/edit the `### XXX-000` section in the matching `docs/standards/*.md` (3-digit id; the heading regex in `test_meta.py` requires it).
2. Add/edit the `Rule(...)` in the matching `rules/*.py` module's `RULES` tuple, same id verbatim.
3. If you add a new rule module, register it in `audit._RULE_MODULES`.
4. `tests/test_meta.py` enforces that documented and implemented id sets are identical — run it.

## Testing

Rule tests in `tests/rules/` exercise each module against synthetic good/bad fixture repos, one pair per language, built by `tests/fixtures/build.py` and exposed via `tests/conftest.py`: a `good_*` repo that passes every applicable rule and a `bad_*` repo that fails every one. When you add a rule, extend both builders for the relevant language so the good repo still passes and the bad repo triggers the new failure. `test_report.py` uses syrupy snapshots (`--snapshot-update` to regenerate). Property tests for the filer use hypothesis.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `millsmillsymills/consistency-check`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles using their default strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
