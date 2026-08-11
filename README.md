# consistency-check

Canonical MCP-server standards and audit tool for the millsmillsymills MCP suite.

The standards in `docs/standards/` are the source of truth; the tool mechanically
enforces them. It walks each target repo, runs the applicable subset of its 96 rule
checks, and emits a markdown gap report — optionally filing the findings as GitHub
issues.

## Running the audit

```bash
uv sync --all-groups                                    # install deps incl. dev group

uv run consistency-check audit                          # dry-run, all repos, prints to stdout
uv run consistency-check audit --repo unifi-mcp         # one repo
uv run consistency-check audit --out reports/           # writes per-repo <name>.md files
uv run consistency-check audit --repo unifi-mcp --apply # files GitHub issues (idempotent)
```

Without `--apply` the filer prints the `gh` calls it would make. With `--apply` it files
one umbrella issue per repo, edited in place on re-run, plus one child issue per
MUST/SHOULD failure, created once. Both are keyed by exact issue title and labelled
`consistency`; children also get `consistency:must` / `consistency:should`. MAY failures
stay inline in the umbrella.

Audited repos are hardcoded in `consistency_check/repos.py` — five Python servers
(`unifi-mcp`, `unraid-mcp`, `gandi-mcp`, `shortcut-mcp`, `flipperzero-mcp`) and one
Go server (`protonmail-mcp`), all under `~/Desktop/Projects/mcp-server-dev`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No MUST failure and no audit error. SHOULD and MAY failures still exit 0. |
| 1 | At least one MUST failure. |
| 2 | Unknown `--repo` name, or a rule check raised an error. |
| 3 | `gh` filer call raised a RuntimeError under `--apply`. |

## Three axes

Each rule carries a **tier**, a **min_stage**, and optionally an **archetype**.

- **Tier** (RFC 2119) — `MUST` blocks merge, `SHOULD` is the default with documented
  exceptions, `MAY` is a preference. Only MUST failures set exit 1; see the exit-code
  table above for the error paths that also exit nonzero.
- **Stage** (`S0`–`S4`) — how complete the server is. A repo declares its stage with a
  `Stage: S2` line in its README `## Status` section. The auditor runs only rules at or
  below the declared stage, marks the rest `n/a`, and lists the next stage's rules as a
  promotion checklist. A repo with no `S`-token is *unstaged*: every rule runs.
  See `docs/standards/stages.md`.
- **Archetype** — where the server can run: `remote-hostable`, `site-local`, or
  `host-local`, declared as a `Deployment: site-local` line in the same `## Status`
  section. It gates the archetype-conditional `MCP-DEPLOY-*` rules.
  See `docs/standards/deployment.md`.

Two MAY-tier meta-rule pairs check the declarations themselves: `MCP-STAGE-DECL` /
`MCP-STAGE-DRIFT` and `MCP-DEPLOY-DECL` / `MCP-DEPLOY-DRIFT` fire when a declaration
is missing or contradicts cheap structural signals.

## Rules

Rule IDs are referenced verbatim by both the standards doc and the rule module.

| Prefix | Rule module | Standards doc |
| --- | --- | --- |
| `MCP-*` | `rules/`: `structure`, `docs`, `tests`, `ci`, `security`, `deps` | `docs/standards/mcp.md` |
| `PY-*` | `rules/python.py` | `docs/standards/python.md` |
| `GO-*` | `rules/go.py` | `docs/standards/go.md` |
| `PROTO-*` | `rules/mcp_protocol.py` | `docs/standards/mcp-protocol.md` |
| `MCP-DEPLOY-*` | `rules/deployment.py` | `docs/standards/deployment.md` |
| `MCP-STAGE-*` | `rules/stage_meta.py` | `docs/standards/stages.md` |

A rule's `check` is a pure `Callable[[Repo], str | None]`: `None` on pass, an evidence
string on fail. A check that raises becomes an `error` finding rather than crashing the
run.

To add one: write the `### XXX-000` section in the standards doc, add the matching
`Rule(...)` to the module's `RULES` tuple, register any new module in
`audit._RULE_MODULES`, and extend the good/bad fixture builders in
`tests/fixtures/build.py`. `tests/test_meta.py` enforces that the documented and
implemented ID sets are identical.

## Development

```bash
uv run pytest -q                              # all tests
uv run pytest tests/rules/test_python.py -q   # one module
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

Rule tests exercise each module against synthetic fixture repos — one `good_*` repo that
passes every applicable rule and one `bad_*` repo that fails every one, per language.
Report tests use syrupy snapshots (`--snapshot-update` to regenerate); filer tests use
hypothesis.
