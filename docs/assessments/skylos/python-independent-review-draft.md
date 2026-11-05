# Independent AI review — DRAFT for owner signoff

Issue [#75](https://github.com/millsmillsymills/consistency-check/issues/75).
Prepared 2026-10-29 by a new Codex AI reviewer, separately from the collecting
agent. This is a draft recommendation for Andrew, not a signed final review,
owner acceptance, scoring permission, or rollout decision. The
[machine-readable draft](python-independent-review-draft.json) records all 30
case judgments and all 21 finding judgments, preserving original IDs, indexes,
hashes and evidence. Every final owner/denominator decision is unset and
`scoring_authorized` is false. Merging this draft would not constitute signoff.

## Evidence and independence

Reviewed the [frozen handoff](python-review-packet.md#independent-review-handoff),
[protocol](README.md), [corpus](../../../assessments/skylos/corpus.json),
[observations](phase-2-observations.json), and cited upstream code at
`4f32409b5aaf913ca249483dc15221118c6c56db`. The review used an isolated local clone
of repository commit `6f77841ad72de1e7b2aee4bcbf9cc0d44f8e23de`; the live checkout
and retained raw outputs were read only. No collecting-agent judgments were
delegated back to the collector. Reading its proposals supplied context, not
ground truth; each draft was checked against source and observations.

Integrity checks independently matched:

- Current GitHub main blobs for the packet JSON/Markdown, protocol, corpus and
  observations to the local reviewed files. Exact-byte and Git blob hashes are
  recorded in the JSON input manifest.
- All 30 original case hashes and observation links, all 21 original finding
  hashes/indexes, and all 90 retained result/stdout/stderr hashes for these units.
- All 23 upstream source-file hashes at the pin, with line contents inspected.
  Four added context anchors expose the actual relative-import skip, the
  subprocess rule ID, and verify's AI selection defaults/predicate.

The registered corpus hash is **canonical JSON**,
`93233d48104537eb6cb999dd1e53381392e98d5867188c6b25b2ff66aa9c58ef`.
Its exact-byte file hash is separately
`b60f33203601d5c00e25dba50c45d2fc9c63ad28f42b32ca73459720c5a36ffe`;
these are different hash conventions, not input drift. The exact-byte observation
hash is `fd357ba5795f3493c8731840340300195fd432c2eaebc7304092bff28faf60c2`.
Hash validation establishes linkage/integrity, not independent reproduction of
scanner behavior. No scanner, corpus program, real snapshot, engine upgrade,
timed repetition or scoring operation was run for this review.

## Draft case decisions

Rows cover both defect and control in each frozen pair. JSON includes each case
separately with complete source lines, evidence references and null owner decision.
“Supported” below is limited to the exact source shape and selected observation.

| Pair | Draft support/outcome | Evidence and limit |
|---|---|---|
| 01 private helper | Support exact pair | `transform` at defect `main.py:1` is uncalled; control calls it at line 3. |
| 02 decorator | Support exact pair; attribution limited | Identity decorator only returns `fn`; callback at line 4 is never called. Control stores at line 3 and invokes at line 8; recognized `register` names also receive reference credit. |
| 03 factory | Support observations; generality unestablished | Positive is ordinary unused `transform`, with no factory. Control stores callback at line 4 and invokes at line 10. Cannot isolate factory inference from name/reference credit. |
| 04 dispatch | Support exact pair | Defect callback omitted from empty map; control stores and invokes it. Extra unread map binding is separate. |
| 05 literal lookup | Support exact pair | Defect method unused; control invokes literal `getattr` at line 5. No arbitrary computed lookup guarantee. |
| 06 optional API | Unmeasured | Both have zero checked references. Typed `client` parameter is outside identified imported-module alias resolver. Missing member in defect is not safe merely because scanner is quiet. |
| 07 subprocess timeout | Unmeasured | Identified timeout rule handles listed network calls, excluding `subprocess.run`. Verify does not emit every quality finding. No applicable selected deadline detector established. |
| 08 subprocess error | Unmeasured | Identified `SKY-L030` handles broad exception handlers with trivial returns, not `check=False` and discarded exit status. No applicable selected return-code detector established. |
| 09 injection | Support exact pair | `input()` concatenated into `shell=True` at line 2; control uses an argument list. Two reports, one injection defect. |
| 10 fixture | Support decorator shape | Ordinary helper unused; `pytest.fixture` receives reference credit. No fixture execution/discovery proof. |
| 11 public export | Support explicit export shape | `_transform` unused; control `__all__` explicitly exports `transform`. Other library conventions unmeasured. |
| 12 local symbol | Support member existence | `helper.py` defines `available`, not imported `missing`; control import verified. |
| 13 positional arity | Unmeasured | Both verify the existence of imported `combine`, not its required positional arguments; the installed signature path is disabled by selected options and does not establish this local arity check. |
| 14 relative import | Existing sibling supported; missing target incomplete | Missing `.missing` produces zero checked/one skipped reference; control `.helper` verifies one reference. Preserve incomplete/nonpassing status. |
| 15 unreachable | Support exact pair | Defect line 3 follows unconditional return; control print precedes return. Policy reports do not diagnose unreachable code. |

For 06–08/13, agree with the packet's bounded support proposals. This is not an
exhaustive proof that Skylos has no other applicable detector. A different
detector claim needs pinned source plus selected-mode evidence; until then these
features remain unmeasured and neither control silence nor language-level
completion supplies feature success. Do not silently narrow the frozen universe
or produce a revised recall denominator.

For 14, recommend **partial existing-sibling coverage, missing-target incomplete**,
not broad relative-import support or a completed accuracy result. The packet's
original anchor stops just before the operative skip; the extended
[lines 342–349](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/ai_defect/python_api_hallucination.py#L342-L349)
show `state.skip("unresolved_relative_import")` at line 348.

## Draft finding decisions

The counts below enumerate objects for review; they are not accuracy metrics.
All 21 reports remain visible. Final precision classifications are unset.

| Objects | Draft factual judgment | Relevance/usefulness and grouping |
|---|---|---|
| Nine seed-location objects in 01–05, 10–12, 15 | Supported | Symbols/lines match the registered defects. Useful within these exact synthetic units. Each keeps its own seed group. |
| `python-04-defect:finding-02`, `handlers` at line 3 | Supported unread binding | A local cleanup hint, incidental to omitted callback; deleting empty map does not repair callback registration. Distinct binding group; no extra seeded callback credit. |
| `python-05-defect:finding-02`, `worker` at line 4 | Supported unread binding | Local cleanup hint; constructor has no custom behavior in this closed source. Distinct from uncalled method. Do not generalize to side-effectful constructors or authorize deletion. |
| `python-09-defect:finding-01` / `finding-02`, `SKY-D209` / `SKY-D212` | Both supported | Same line-2 shell sink and same injected input. Recommend one underlying injection group; retain both objects and do not claim two unique useful defects. |
| Eight `SKY-R101`–`SKY-R104` objects, four each in 15-control and 15-defect | Factual configuration absence supported | Catalogued advice; not unreachable diagnoses. Utility for these minimal synthetic units is not demonstrated. Final true-positive semantics under precision remain unresolved for owner decision. |

For policy advice, the fixture has no declared type-check/lint/gate/pre-commit
requirement. Adding a scanner's own gate is not independently demonstrated to
repair a useful defect here. I therefore recommend recording **true absence,
incidental advice, no demonstrated utility as a seeded defect**. Do not equate
“factually true” with an adjudicated precision true positive; do not equate
“not a seeded defect” with a factual false alarm. The protocol needs an explicit,
consistent owner interpretation before these eight enter any numerator, while
all remain in the reported universe. Unknown precision treatment blocks a claim.

The source independently supports this distinction:
[policy emission](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/quality/policy.py#L419-L482),
[advice catalog](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/catalog.py#L438-L453).
Identical rule text across the two isolated case repositories is not one
underlying defect: these are different inputs with separate missing policies.
No broad cross-case deduplication is proposed.

Recommended consistent grouping rule: same evaluation unit, same source
operation, same underlying defect/remedy. Apply it throughout the complete
review universe. The two shell reports meet it; the unread bindings versus
unused functions, and the distinct absent policy kinds, do not. Final owner
acceptance and denominator application remain pending.

## Reachability and remaining boundaries

Toy controls explicitly reference/call registry entries and recognized names
receive heuristic credit. They show source-level liveness or intentional export
in those units. They do not establish all framework shapes, dynamic discovery,
real MCP registration inventories, or actual runtime reachability. No source
removal follows from this draft.

Go remains separately deferred on the pinned engine/CLI `symbols.refs: null`
contract failure. This review supplies no changed-pin fix, native-engine
substitution, Go suppression result or replacement observation. Real-server
registration inventories, baselines/overlap, independent real-finding review,
20 timed repetitions after warm-up, and six rollout decisions remain gated.
Issue #75 stays open. No precision, recall, p95 or adoption conclusion follows.

## Exact owner signoff questions

1. Do you accept the 30 draft case judgments, keeping 06–08/13 unmeasured and
   14-defect incomplete, without changing the frozen universe or authorizing scores?
2. Do you accept the nine seed-location matches and two additional unread
   bindings as truthful, with bindings only local cleanup hints and not extra
   seeded defects?
3. Do you accept both shell reports as truthful evidence of one underlying
   injection defect and the same-operation grouping policy across the universe?
4. For all eight policy objects, do you accept factual absence but no demonstrated
   utility as seeded defect findings, with final precision classification left
   unresolved until an explicit consistent interpretation under the frozen method?
5. Do you accept the limited registration/export claims and leave real-server
   reachability, Go, measurements, scoring and adoption gates pending?

Final reviewer identity/date/signature, owner decision/date, denominator choices,
per-case/per-finding owner decisions and precision classifications remain null
in the JSON record. Andrew can accept or dispute individual drafts with rationale;
a future final record must preserve unresolved items and evidence provenance.
