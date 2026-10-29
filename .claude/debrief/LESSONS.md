# Lessons

Repo-specific lessons for `consistency-check`. Machine-wide truths live in
`~/.claude/debrief/LESSONS.md`.

These lessons originated in earlier investigations and were checked against the
current implementation before merging. Historical failures below describe what
to guard against, not a list of defects still present.

## Evidence is published to public issues

- Treat every string interpolated into `Finding.evidence` as destined for a public GitHub issue about a private target repo. The renderer fences, normalizes, and truncates evidence, but these operations do not redact secrets. `audit-out/` and `audit-out-validation/` are ignored and untracked; keep them that way.
- `_MAX_EVIDENCE` is a length bound, not a confidentiality guarantee. The fixture contract currently allows 400 characters and path lists commonly cap at five. Evidence should identify a rule subject or declaration site rather than quote source; do not mistake a shorter source span for safe evidence.
- `_MAX_PROSE_HITS = 5` bounds one result, not cumulative disclosure across repeated audits. Keep evidence to locations and public rule subjects rather than captured private prose.
- `test_evidence_contract.py` measures only `str` returns from the `bad_*` fixtures. `NotApplicable.reason` goes through the same renderer but is not measured, and branches the fixtures do not exercise are unbound. Keep decline reasons constant and add focused fixtures for sensitive branches.
- Review evidence from PROTO-011, PROTO-012, and PROTO-017 before quoting findings in a public PR body; never paste private source or credential values.

## Rule authoring

- Choose the source accessor for the subject: `code_only()` for code, `code_and_literals()` when literal values matter, and raw text only for deliberately coarse checks. Comments must be stripped before literals; comment-blind literal stripping can hide real code after a quote in prose.
- Anchor on call syntax (`uvicorn\.run\(`, `http\.ListenAndServe\(`), not a bare substring. `# TODO: streamable HTTP is not supported yet` passes a MUST that a bare substring fails.
- A rule that reads a corpus containing its own declaration line is self-satisfying: `MCP-DEPLOY-DOCS` matched `Deployment: remote-hostable` in the `## Status` block, so a README saying "we have no plans to deploy this" passed.
- Before widening a shared corpus helper, enumerate its callers. Widening `_ci_corpus` for MCP-025 (SHOULD) silently widened MCP-026 (MUST) too.
- Before adding a rule, check whether an existing one already owns the assertion, and scope both to the same corpus. MCP-018 scans `release.yml` only while MCP-DEPLOY-ARTIFACT scans all workflows, so one repo fails one and passes the other for a single root cause.
- Keep maturity stage and RFC-2119 tier independent. The documented stage map places PROTO-023 through PROTO-026 at S4/SHOULD; change that policy explicitly in the standards, implementation, and tests rather than using either axis as an ad hoc deferral knob.
- Ship a "Known limit" paragraph with any name-mention regex; it cannot distinguish construction from mention. PROTO-022 already sets the convention.

## Driver and report contracts

- `audit.py` short-circuits stage-gated and archetype-gated rules to `n/a` before the check runs, so `_UNDECLARED` branches inside `rules/deployment.py` are dead in production. The suite currently pins contradictory behavior for one repo shape.
- `n/a` covers several causes. Preserve `applicable=False` for language mismatches so promotion checklists exclude rules a repo can never clear, and preserve `unevaluated` for checks that could not grade it.
- When you add a third outcome to a two-outcome contract, audit every consumer: renderer, exit code, promotion checklist, and sweep. A corrupt `.git/index` turned a committed `.env` from fail/exit 1 into n/a/exit 0 with the umbrella reporting "compliant through S3 gates".
- Exit-code semantics are restated in README and CLAUDE.md and have already drifted from each other. `__main__.py` is the only source of truth; point at it rather than restating it.

## Tests

- Keep the stage contract document-derived: `tests/test_min_stage_map.py` parses the authoritative `stages.md` table and its closure default, including explicit meta-rule assignments. A hand-copied dictionary previously allowed docs-only policy changes to drift with the suite green.
- `test_meta.py` enforces only rule-ID parity, so standards prose drifts from behavior undetected.
- A good/bad fixture pair cannot protect every conditional branch. Keep focused deployment tests for remote-hostable, site-local, host-local, and undeclared repos alongside the broad sweep; site-local transport deliberately has no additional constraint.
- `test_sweep.py` distinguishes `None` (pass) from `NotApplicable` (ungraded), and validates its exemption set. Preserve that distinction: a bad-fixture sweep alone still does not prove a check evaluated every relevant branch.
- Validate new rules with focused fixtures for code fences, comments, literal values, and applicability gates. When registry checkouts are available, compare local audit output too; keep private target evidence out of committed artifacts.
- Diff the audit's real output on `main` against the merged branch across all six repos before believing a "no behavioral change" claim.
