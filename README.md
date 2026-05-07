# consistency-check

Canonical MCP-server standards and audit tool for the millsmillsymills MCP suite.

## Running the audit

```bash
uv run consistency-check audit                          # dry-run, all repos, prints to stdout
uv run consistency-check audit --out reports/           # writes per-repo .md files
uv run consistency-check audit --repo unifi-mcp --apply # files GitHub issues (idempotent)
```

Standards live in `docs/standards/`. Each rule ID (`MCP-001`, `PY-014`, `GO-007`, `PROTO-003`) is referenced verbatim by both the standards file and the matching rule module under `consistency_check/rules/`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | All applicable rules passed (or only MAY findings). |
| 1 | At least one MUST failure. |
| 2 | Unknown `--repo` name, or a rule check raised an error. |
| 3 | `gh` filer call raised a RuntimeError under `--apply`. |
