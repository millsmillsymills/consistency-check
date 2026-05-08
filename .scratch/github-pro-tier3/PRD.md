# GitHub Pro — Tier 3 follow-up decisions

Status: needs-triage
Created: 2026-05-08

## Background

After subscribing to GitHub Pro, we applied a Tier 1–2 baseline across the four MCP repos (unifi/unraid/gandi/protonmail-mcp) plus marked unraid-mcp as a template repo. Three Tier 3 ideas were deferred for explicit decision:

1. Cross-repo GitHub Project (v2) for the consistency-check umbrella + child issues.
2. Migrate the four repos into a GitHub organization.
3. Encode the new GitHub-config rules (CODEOWNERS, rulesets, security baseline, devcontainer, etc.) as new MCP-025..030 audit rules.

Each is captured in `issues/` for individual decision. None of the three is a prerequisite for the others.

## Decision deadline

None — these are quality-of-life improvements that can wait. Revisit when the next MCP server is being scaffolded (item 13 becomes much more attractive at that point).
