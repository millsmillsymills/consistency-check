# Lessons

Repo-specific lessons for `consistency-check`. Machine-wide truths live in
`~/.claude/debrief/LESSONS.md`.

## Evidence is published to public issues

- Treat every string interpolated into `Finding.evidence` as published verbatim to a public GitHub issue about a private target repo. `audit-out/*.md` is tracked on `origin/main`, which amplifies anything that slips.
- `_MAX_EVIDENCE` is a length bound, and length is the wrong axis. Raising it 200 to 400 for a legitimate five-filename list put a known 245-char source-span leak under the bar. Bound the shape instead: reject a newline, reject `=` inside parens, cap path lists at three.
- `_MAX_PROSE_HITS = 5` is not a cap but a progressive oracle: fix the top hit, re-run, and the next private pattern publishes.
- `test_evidence_contract.py` measures only `str` returns from the `bad_*` fixtures. `NotApplicable.reason` goes through the same renderer (`report.py:168,177`) and is never measured, and any branch the fixtures do not exercise is unbound. Assert over the real registry when checkouts are present, or over every rule.
- PROTO-011, PROTO-012, and PROTO-017 findings should never appear in a public PR body.

## Rule authoring

- Route text checks through `code_only()`, never `strip_literals()` on raw text. Comments must be stripped before literals, or one unpaired `'''` or backtick in a comment blanks every line to the next delimiter and the rule silently passes.
- Anchor on call syntax (`uvicorn\.run\(`, `http\.ListenAndServe\(`), not a bare substring. `# TODO: streamable HTTP is not supported yet` passes a MUST that a bare substring fails.
- A rule that reads a corpus containing its own declaration line is self-satisfying: `MCP-DEPLOY-DOCS` matched `Deployment: remote-hostable` in the `## Status` block, so a README saying "we have no plans to deploy this" passed.
- Before widening a shared corpus helper, enumerate its callers. Widening `_ci_corpus` for MCP-025 (SHOULD) silently widened MCP-026 (MUST) too.
- Before adding a rule, check whether an existing one already owns the assertion, and scope both to the same corpus. MCP-018 scans `release.yml` only while MCP-DEPLOY-ARTIFACT scans all workflows, so one repo fails one and passes the other for a single root cause.
- Do not overload a scope axis as a deferral knob. `min_stage=S4` to mean "not yet actionable" puts protocol rules on the S4 promotion checklist beside real distribution rules; `Tier.MAY` at the default S3 renders inline and is skipped by the filer, which is the stated intent.
- Ship a "Known limit" paragraph with any name-mention regex; it cannot distinguish construction from mention. PROTO-022 already sets the convention.

## Driver and report contracts

- `audit.py` short-circuits stage-gated and archetype-gated rules to `n/a` before the check runs, so `_UNDECLARED` branches inside `rules/deployment.py` are dead in production. The suite currently pins contradictory behavior for one repo shape.
- `n/a` is overloaded for stage-gated and language-inapplicable, so a Python repo's promotion checklist lists `GO-*` rules it can never clear.
- When you add a third outcome to a two-outcome contract, audit every consumer: renderer, exit code, promotion checklist, and sweep. A corrupt `.git/index` turned a committed `.env` from fail/exit 1 into n/a/exit 0 with the umbrella reporting "compliant through S3 gates".
- Exit-code semantics are restated in README and CLAUDE.md and have already drifted from each other. `__main__.py` is the only source of truth; point at it rather than restating it.

## Tests

- `tests/test_min_stage_map.py` hand-copies the `stages.md` table, so the two drift with the suite green. `test_meta.py` sets the precedent of parsing the doc instead.
- `test_meta.py` enforces only rule-ID parity, so standards prose drifts from behavior undetected.
- A good/bad fixture pair proves nothing when both land in the same trivially-passing branch. The good fixtures declared `site-local`, for which TRANSPORT returns `None` unconditionally, and the bad ones declared no archetype: four archetype rules had zero coverage in both directions with a green sweep.
- `test_sweep.py` scores a pass as `check(repo) is None`, so a rule returning `NotApplicable` on the bad fixtures escapes `_CANNOT_FAIL` silently.
- Run a new rule against the six real registry repos before merging, not just the fixtures. MCP-027 fired 229 times on this repo, and `^@` matches `@mcp.tool()` inside every FastMCP README code fence.
- Diff the audit's real output on `main` against the merged branch across all six repos before believing a "no behavioral change" claim.
