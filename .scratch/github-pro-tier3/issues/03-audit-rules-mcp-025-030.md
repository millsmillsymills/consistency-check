# 03 — Add MCP-025..030 audit rules for GitHub-config consistency

Status: needs-triage
Type: decision
Created: 2026-05-08

## Question

Should we add new audit rules to the consistency-check tool that grade GitHub repo *administration* (rulesets, CODEOWNERS, security baseline, devcontainer, templates) the same way we grade file/code shape today?

## Proposed rule IDs

| ID | Tier | Rule |
|---|---|---|
| MCP-025 | MUST | Repository ruleset enforced on default branch (PRs required, status checks, linear history) |
| MCP-026 | MUST | `.github/CODEOWNERS` present (referenced by ruleset when team grows past one) |
| MCP-027 | MUST | `security_and_analysis` baseline enabled: secret_scanning, secret_scanning_push_protection, dependabot_security_updates |
| MCP-028 | SHOULD | `delete_branch_on_merge: true` |
| MCP-029 | SHOULD | `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` and `.github/PULL_REQUEST_TEMPLATE.md` present |
| MCP-030 | SHOULD | `.devcontainer/devcontainer.json` present |

## Why this is a decision

Pros:
- Makes the audit tool the source of truth for *all* per-repo consistency, not just files in the working tree.
- Catches drift when a new repo skips a Pro setting we forgot to apply.
- Pairs naturally with future template-repo + org-migration work (issues 01/02).

Cons:
- The audit tool currently runs offline against a local repo path. These new rules need to call the GitHub API (`gh api repos/<slug>/rulesets`, `repos/<slug>` for security flags, etc.). That changes the architecture (network access, rate limits, gh-auth precondition).
- We'd need to thread a `--github-slug` flag (or read it from `git remote get-url origin`) into the rule context.
- MCP-024 (dep age) is already a stub for the same network-access reason. Adding more network-dependent rules is a slippery slope.

## Suggested options

- **a) Add all six.** Build a small `github_api.py` helper, gate it behind `--check-github` flag (off by default, on in the audit script). Filer already requires gh auth in Phase 3; this just extends the same context.
- **b) Add only MCP-025/027 (the highest-leverage ones).** CODEOWNERS file presence is already covered by file-shape rules; templates and devcontainer are nice-to-have.
- **c) Skip — keep audit offline-only.** Track GitHub-config consistency via a separate weekly script outside the consistency-check tool.

## Recommendation

**a)** Add all six, gated behind a single `--check-github` flag. The audit tool is already the right home for this, and we're already calling `gh` in Phase 3. Doing it once is cheaper than building a parallel script.

## Comments
