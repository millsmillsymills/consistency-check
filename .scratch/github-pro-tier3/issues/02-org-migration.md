# 02 — Migrate the 4 MCP repos into a GitHub organization

Status: needs-triage
Type: decision
Created: 2026-05-08

## Question

Should the four MCP repos move from the personal account `millsmillsymills` to a GitHub organization (e.g., `mills-mcp` or `millsymills`)?

## Why this matters

A GitHub org enables:
- A `.github` repo whose `CODEOWNERS`, default issue templates, default workflows, and FUNDING.yml apply to *every* repo in the org. Today we copy these into each repo and they drift.
- Org-level rulesets — one ruleset definition that targets all repos, instead of four per-repo rulesets we just applied. Solves the exact "MCP-025 rulesets enforced" check (issue 03) by construction.
- Org-level secret management for Actions (one place to rotate the gh token, the consistency-check audit token, etc.).
- Cleaner template repository UX — a templated repo created in the org inherits org defaults.

The cost: migrating repos is one-click but breaks `git remote` URLs (redirects work, but PRs/issues references that hardcode `millsmillsymills/<repo>` need updating); CI tokens may need refresh; npm/PyPI publishing identity changes if applicable.

## Suggested options

- **a) Migrate now.** Create org `mills-mcp` (or similar), transfer all 4 repos, add `.github` repo with shared CODEOWNERS + workflow templates, replace per-repo rulesets with one org-level ruleset. Update CLAUDE.md / `mcp_consistency_refs.md` slugs.
- **b) Migrate when we add a 5th MCP server.** The marginal value is low at 4 repos; high once we have 5+.
- **c) Skip permanently.** Stay personal-account; accept the per-repo duplication.

## Recommendation

**b)** Hold until repo #5. The Tier 1–2 baseline we just applied does the per-repo job; org migration is the right move when we're literally creating MCP server #5 from the unraid template.

## Comments
