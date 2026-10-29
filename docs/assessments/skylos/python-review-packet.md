# Frozen Python support and adjudication packet

Issue [#75](https://github.com/millsmillsymills/consistency-check/issues/75).
This interprets the existing [sample-0 observations](phase-2-results.md).
It adds **no scanner runs, changed inputs, changed pins, scores or adoption claim**.
The [JSON review packet](python-review-packet.json) preserves all 30 Python cases
and all 21 finding objects. Every judgment is a proposal from the collecting
agent; independent review remains pending. Merging this packet does not sign it.

The packet references the exact observation-file hash and unchanged corpus hash
`93233d48104537eb6cb999dd1e53381392e98d5867188c6b25b2ff66aa9c58ef`.
Case hashes preserve the original registered expectations. Finding indexes are
zero-based within each observation's `findings` array; hashes cover those original
objects. No silent case or incidental finding is removed from the review universe.
All 23 source anchors were checked against the clean pinned upstream commit
`4f32409b5aaf913ca249483dc15221118c6c56db`, including Git blob equality,
file SHA-256 and line boundaries. Their descriptions are source-backed inferences,
not new scanner guarantees; the JSON provides commit-pinned URLs and locations.

## Proposed support mapping

A complete language-level receipt cannot establish every feature. These proposals
do not authorize a revised scoring denominator.

| Pair | Proposal | Observed evidence / limit |
|---|---|---|
| 01 private helper | Implemented for this shape | Unused `transform` reported; directly called control quiet. |
| 02 decorator registration | Implemented for toy shapes | Identity-decorated callback reported; registered/called control quiet. Name heuristics also credit decorators. |
| 03 factory registration | Implemented for toy shapes | Plain unused positive reported; factory-registered/called control quiet. Positive overlaps ordinary unused-function coverage. |
| 04 dispatch map | Implemented for this shape | Omitted callback reported; referenced control quiet. Extra `handlers` binding needs judgment. |
| 05 string lookup | Implemented for this shape | Unused method reported; literal `getattr` control quiet. Extra `worker` binding needs judgment. |
| 06 optional instance API | Outside identified module surface | Typed parameter is not an imported module alias; both units have zero checked references. Keep feature unmeasured. |
| 07 subprocess deadline | No matching selected detector established | Identified timeout detector has a network-call allowlist without `subprocess.run`. |
| 08 subprocess error | No matching selected detector established | Identified swallowed-error detector examines broad exception handlers, not ignored return codes. |
| 09 shell injection | Implemented for this shape | Two rules report the same input-controlled shell call; overlap group is proposed. |
| 10 intentional fixture | Implemented for decorator shape | Ordinary helper reported; `pytest.fixture` receives reference credit. Not proof of arbitrary fixture execution. |
| 11 public entry point | Implemented for explicit export | Private helper reported; `__all__` export respected. |
| 12 local API symbol | Implemented for this shape | Missing imported member reported; existing imported member verified. |
| 13 local positional arity | Outside identified existence check | Import verification establishes symbol existence, not required argument count. |
| 14 relative import | Incomplete on missing target | Missing sibling has one skipped/zero checked reference; existing sibling verified. |
| 15 unreachable statement | Implemented for this shape | Statement after return reported; control has no unreachable report. Both also emit policy advice. |

### Source evidence for silent/incomplete cases

Case 06 resolution follows imported local-module aliases rather than arbitrary
typed receiver instances: see
[member resolution](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/ai_defect/phantom_refs.py#L2280-L2330)
and [alias lookup](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/ai_defect/phantom_refs.py#L2332-L2351).
Zero references are consistent with this scope, not evidence that the missing
method is safe or that guard-sensitive instance-member checking is supported.

Case 07's identified
[timeout detector](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/quality/logic_security.py#L3879-L3903)
uses a [network-call set](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/vibe_dictionary.py#L331-L350).
Case 08's identified
[swallowed-error detector](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/quality/logic_maintainability.py#L3317-L3343)
handles broad exception handlers. Neither establishes the seeded subprocess
feature. This is bounded source evidence about selected checks, not all Skylos
capabilities. An independent reviewer may supply a different applicable detector;
until then, silent defect/control pairs remain unmeasured, not true negatives.

For 13, local import coverage verifies member existence. The separate installed
signature checker is
[gated with dependency checks](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/analyzer.py#L5452-L5500),
disabled by the registered invocation. Its
[target checker](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/ai_defect/api_signature_hallucination.py#L557-L584)
checks keyword acceptance, not required positional arguments for the local
`combine(left, right)` seed. Do not enable a different mode or revise the seed
after observing this result without separate reviewed preregistration.

Case 14's
[relative-import path](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/ai_defect/python_api_hallucination.py#L339-L347)
explicitly records a skipped unresolved import. It remains incomplete despite an
empty findings array and a successful sibling-import control.

## Proposed finding adjudication

Every finding has its own ID, original index/hash, source references, rationale
and pending review status. These proposed groups preserve all reported objects:

| Group | Objects | Independent judgment needed |
|---|---:|---|
| Seed-location matches in 01–05, 10–12 and 15 | 9 | Confirm location/symbol semantics and class support. |
| `SKY-D209` / `SKY-D212` in 09 | 2 | Same line-2 shell call; proposed one underlying defect, both reports retained. |
| Extra `handlers` / `worker` in 04/05 | 2 | Bindings are never read; judge truth/usefulness separately from intended seed. |
| `SKY-R101`–`SKY-R104` in both 15 inputs | 8 | Absent fixture policies are advice, not unreachable-code diagnoses. |

Policy reports are neither automatically false positives nor automatically
excluded from reported positives. Source
[emits absent-policy reports](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/quality/policy.py#L419-L482)
and [catalogues them as advice](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/skylos/rules/catalog.py#L438-L453).
Their relevance and consistent precision treatment need review under the frozen
method; deleting them after seeing their cost would not establish the pilot gate.

Toy registration controls contain direct references/calls, and the scanner also
credits recognized decorator names. Results do not isolate each rescue mechanism,
prove all framework shapes or establish real MCP reachability. No source removal
is authorized by any proposed true-positive judgment.

## Independent-review handoff

The collecting agent prepared and checked this packet; that is not independent
review. Reviewer identity/date are null, all decisions pending and
`scoring_authorized` false. An owner or different reviewer needs to:

1. Confirm/dispute support proposals for silent 06–08/13 without silently
   narrowing the frozen recall denominator; keep unmatched features unmeasured
   and disputed conclusions unknown.
2. Preserve incomplete 14 and decide its supported-feature status.
3. Judge the two extra bindings and eight policy objects for truth/usefulness/
   relevance without hiding them in a reduced precision denominator.
4. Accept/reject shell-call grouping and apply one consistent underlying-defect
   policy to the complete review universe.
5. Confirm toy-registration limits. Real-server registration inventories,
   baselines/overlap and independent real-finding review remain necessary.
6. Record reviewer identity, date, rationale, evidence and unresolved items in a
   separate reviewed decision record. Keep thresholds/corpus/modes/pins frozen;
   changed replacement observations need preregistration.

No denominator or accuracy score is final before those decisions. This packet
does not supply independent real-server review, 20 timed runs or six rollout
decisions. #75 stays open. The pinned Go contract failure remains a defer/blocker;
no changed-pin resolution or replacement observations are proposed here.
