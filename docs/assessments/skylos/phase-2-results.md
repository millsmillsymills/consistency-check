# Skylos capability and Python sample-0 observations

Issue [#75](https://github.com/millsmillsymills/consistency-check/issues/75).
Collection infrastructure: PRs #88 and #89. Inputs remain corpus revision 1;
seven extra suppression probes remain outside its scored denominator.
The [sanitized observation record](phase-2-observations.json) contains 41 unique
units, raw-artifact hashes, coverage, findings, suppressed findings, single-run
wall times, diagnostic contexts and the native/resume exercises.

**This phase does not establish precision, recall, p95 runtime or adoption.**
Python sample 0 has 29 structurally complete units and one incomplete unit.
Go's full 30-case corpus was not collected because capability prerequisites failed.
No real server snapshot was scanned or modified, and no corpus program ran.

## Environment and prerequisites

The isolated Skylos 5.1.5 installation, all 68 package payloads, dependency lock,
launcher, host identity and source-built Go engine matched the profile from #88.
The frozen corpus SHA-256 is
`93233d48104537eb6cb999dd1e53381392e98d5867188c6b25b2ff66aa9c58ef`;
the environment identity SHA-256 is
`6b12b155131cc4274a27d4de86d6ceae13318fef8219989bb5f7afea09e119ca`.
The collector was committed before use; probe registration began at `9db55ff`,
and collection used the code present at `d308958`, now merged through #89.
The record includes the exact plan/collector hashes and captured UTC/host load.

Pinned source-scan and verify help confirm the registered flags. JSON doctor
selected the exact `SKYLOS_GO_BIN` engine and reported it available. Hook
self-tests were explicitly disabled; doctor reported no installed agent hooks.
Every process group had a 120-second deadline. Registry lookup, upload, models,
tracing, behavioral execution and global installation were outside this phase.

The first diagnostic and unit attempts exposed runner/adapter mismatches:
command-overview help, invalid empty TOML, summarized skip reasons, and omitted
empty finding arrays. These were corrected in #89 against the pinned source and
actual outputs, with regression tests. Sources, expectations and decision gates
were unchanged. Earlier attempts remain present and superseded rather than
being edited into successful runs.

## Suppression and selected-mode coverage

| Probe | Observed result |
|---|---|
| Python unsafe eval, no marker | `SKY-D201` active |
| Python matching `ignore[SKY-D201]` | `SKY-D201` retained under `suppressed`, absent from active findings |
| Python legacy `skylos-ignore` | `SKY-D201` active |
| Python wrong-rule `ignore[SKY-D202]` | `SKY-D201` active |
| Go unused helper, no marker or either marker spelling | All three incomplete; suppression behavior is unmeasured |

The four selected Python dead-code, verify, security and quality units returned
complete structural coverage. Go verify and the selected security input also
completed, but Go dead-code/quality inputs failed native analysis. These selected
units establish only their recorded scope; they do not prove every seeded class
is supported or that real tool registrations are understood.

Direct native diagnostics isolate the Go failure. `go-01-defect` returned exit 0
with `symbols.refs` equal to JSON `null`; the pinned CLI's
`skylos/engines/go_contract.py` requires a list. `go-09-defect` returned a list
with seven references and completed through the CLI. At the pinned source,
`cmd/skylos-go/main.go` initializes an empty `SymbolData` and appends references
only when present, while `internal/output/output.go` serializes the slice without
normalizing an empty slice. This explains the observed zero-reference failure.
Both diagnostics left inputs unchanged. The engine, output and cases were not
patched to bypass its contract. Availability in doctor is insufficient coverage.

## Frozen Python sample 0

All 15 defect/control pairs were observed in their registered modes. The table
summarizes reported evidence, not an accuracy score or final adjudication.

| Family / case | Defect observation | Control observation |
|---|---|---|
| Private function / 01 | `transform` reported unused | No selected findings |
| Decorator registration / 02 | `transform` reported unused | No selected findings |
| Factory registration / 03 | `transform` reported unused | No selected findings |
| Registry dispatch / 04 | `transform` and `handlers` reported unused | No selected findings |
| String lookup / 05 | `transform` and `worker` reported unused | No selected findings |
| Optional API / 06 | No findings; zero references checked | No selected findings |
| Subprocess timeout / 07 | No findings | No selected findings |
| Subprocess error / 08 | No findings | No selected findings |
| Subprocess injection / 09 | `SKY-D209` and `SKY-D212` | No selected findings |
| Intentional fixture / 10 | `sample_data` reported unused | No selected findings |
| Public entry point / 11 | `_transform` reported unused | No selected findings |
| Local API symbol / 12 | `SKY-L012` | No selected findings |
| Local API arity / 13 | No selected findings | No selected findings |
| Relative import / 14 | **Incomplete:** unresolved relative import, zero checked and one skipped reference | Complete, no selected findings |
| Unreachable statement / 15 | `SKY-UC001` plus four policy findings | Four policy findings |

Case 14 is not a true negative or a successful recall sample. Missing findings
in cases 06–08 and 13 also cannot be treated as evidence of correctness: feature
support and scope must be adjudicated before forming a supported-class recall
denominator. Incidental policy findings, extra unused symbols and overlapping
security rules need classification/deduplication before any precision claim.
The benign unreachable control demonstrates why “has findings” alone is not a
ground-truth classifier: it reports absent tooling policy, not unreachable code.

## Retained evidence and actual resume

The local store retains 72 scanner attempts across adapter revisions 1–3,
including 16 invalid outputs and 14 incomplete attempts. There are 41 latest
unique units at revision 3: 35 complete and six incomplete, counting the separate
suppression and selected Go probes. These counts describe artifact integrity,
not passing pilot gates. No old result was overwritten or averaged into success.

A second language-scoped sample-0 invocation exited 2, reused all 29 matching
completed Python units, and retried only `python-14-defect`, which remained
incomplete. Exactly one new attempt appeared, and every previous result file's
hash stayed unchanged. There is no completion receipt for that incomplete unit.

Raw stdout/stderr, diagnostics, complete receipts, rejected attempts and native
outputs remain under ignored `audit-out/skylos/`. The public record contains
selected normalized fields and SHA-256 links to local raw artifacts. Absolute
workspace/input paths are replaced with `<workspace>` / `<inputs>`; no owner
source, credentials or real-server findings are included. The record is not a
replacement for the retained raw evidence.

## Remaining gates

Keep #75 open. Go requires a reviewed pinned engine/CLI solution or an explicit
unsupported/defer decision; substituting a release or changing inputs requires
new preregistration before replacement observations. Python requires explicit
support/adjudication for silent and incomplete classes. Accuracy thresholds
remain unchanged and unscored. The 20 timed repetitions have not run, so the
single-run times in the record support no p95 claim.

Real-server work remains gated on representative-role/registration inventories,
baseline verification and independent finding adjudication, followed by suite
overlap, complete runtime sampling and all six rollout decisions. No new MUST or
MAY/advisory standard is proposed by these limited observations.
