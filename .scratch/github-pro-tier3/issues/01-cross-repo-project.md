# 01 — Cross-repo GitHub Project (v2) for consistency-check umbrellas

Status: needs-triage
Type: decision
Created: 2026-05-08

## Question

Should we create a single GitHub Projects (v2) board that pulls in the 4 consistency-check umbrella issues (#156 unifi, #113 unraid, #45 gandi, #18 protonmail) and their 58 children, so they're trackable in one place across the four repos?

## Why this is a decision and not a no-brainer

Pros:
- One view for all consistency-related work across the suite.
- Status fields, custom views (by-tier, by-repo, by-rule-id) for spotting drift.
- Project (v2) is free; Pro doesn't gate it. Costs ~30 min to set up.

Cons:
- The audit tool already produces per-repo markdown reports (`audit-out/`). A Project board duplicates that view.
- Re-running the audit is the source of truth. A Project board can drift if children are closed/added without updating the board.
- Adds a second place to update issue status.

## Suggested options

- **a) Build it.** Create one project, add the 4 umbrellas + 58 children, add views for tier (must/should) and repo. Wire issue auto-add via `gh project item-add`.
- **b) Skip for now.** Keep `audit-out/` markdown as the source of truth; revisit if a second teammate joins.
- **c) Lighter touch.** Add only the 4 umbrellas to a project; let umbrella children stay tracked in their repo.

## Recommendation

**c)** Add the 4 umbrellas to a single project for the executive view, but don't drag in the 58 children. Re-running the audit remains canonical.

## Comments
