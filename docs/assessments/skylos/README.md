# Skylos advisory pilot: preregistered protocol

Issue: [#75](https://github.com/millsmillsymills/consistency-check/issues/75).
Status: protocol and snapshot inventory only; no benchmark outcomes measured.
Registered: 2026-10-28, America/Los_Angeles, after completion of the two initial
Brooks sweep cycles. This is issue-driven assessment work, not another sweep.

## Source and capability pins

Assess Skylos v5.1.5 at upstream commit
`4f32409b5aaf913ca249483dc15221118c6c56db`. The
[release record](https://github.com/duriantaco/skylos/releases/tag/v5.1.5) names
that target commit. Capability claims below come from its
[pinned README](https://github.com/duriantaco/skylos/blob/4f32409b5aaf913ca249483dc15221118c6c56db/README.md),
and are claims to verify during the pilot, not measured endorsements.

- Python: upstream advertises dead-code, security, quality, and local API proof.
- Go: upstream advertises dead-code analysis and partial security/quality;
  dead-code/security require the matching native `skylos-go` engine. Workspace
  API proof has a separate support/coverage result. A Python CLI being installed
  does not establish Go coverage; capture `skylos doctor` before any Go run.
- Core scans are local and model-free. `skylos agent verify` uses a model and is
  outside this deterministic pilot. Dependency/CVE modes can query registries.
  The pinned verifier documents `--no-dependency-hallucinations` for disabling
  package-existence lookups.

Before running, record the exact wheel/source artifact hashes, all resolved
dependencies and hashes, native-engine identity, Python/Go versions, OS/CPU,
configuration, command help, and supported result-schema versions. Do not
silently substitute a newer release, engine, or model. If the native engine is
missing or mismatched, Go dead-code/security is **unmeasured**, never passing.

## Immutable inputs

`snapshots.json` records six local committed heads observed with no tracked
working-tree changes. These are evaluation inputs, not current rollout claims.
Export committed trees to disposable directories; leave live checkouts alone.
Ignore untracked files, local environments, credentials, and caches. A changed
or unavailable commit invalidates that unit rather than selecting another head.

Primary pilot roles:

| Snapshot | Role | Required characterization before scoring |
|---|---|---|
| unraid-mcp | Python dynamic-registration candidate | Inventory decorators/factories, dispatch/string lookups, and registered tools. |
| unifi-mcp | Python write/destructive-gate candidate | Inventory read/write registration, opt-in guards, and optional APIs. |
| protonmail-mcp | Go server | Verify native-engine availability and separate workspace-proof coverage. |

The two Python roles are hypotheses to confirm in the frozen trees. If a role is
absent, register and explain the replacement before scanning or scoring it.
The remaining three servers are held for suite-wide unique-finding adjudication
and rollout decisions. Preserve registration inventories as a non-removal guard.

## Benchmark and adjudication

Create 15 seeded defects and 15 benign controls **per supported language**,
versioned separately from the real snapshots. Register each case's rule family,
expected finding location/category, ground truth, and unsupported conditions
before inspecting scanner output. Include all of these families, with at least
one defect/control pair each:

1. Decorated/factory-registered or otherwise dynamically reachable tools.
2. String lookup and registry dispatch.
3. Optional API availability and guarded access.
4. Subprocess error handling and timeout behavior.
5. Intentional test fixtures and public/library entry points.

Use remaining cases for direct unused private code, local API mistakes, and
negative controls representative of the pinned scanner's declared scope.
Do not label an unsupported family as a true negative. Synthetic source is
publishable; private target source and unsanitized findings remain local under
ignored `audit-out/skylos/`.

Run the existing Ruff/ty checks on each Python snapshot and its configured Go
checks on the Go snapshot, recording exact versions, configuration, commands,
exit codes, and output. Record absent baseline tooling as unmeasured. Separately
run selected deterministic Skylos families so that dead-code, security, quality,
and workspace proof have distinct coverage and cost results. Confirm their
exact supported flags from the pinned CLI help before recording commands in the
run manifest. Registry-dependent, cloud, LLM, tracing, fix, and comment-posting
modes are outside this pilot.

For real findings, record a human-readable rationale and evidence location for
every true/false/unknown judgment. Deduplicate overlapping findings by underlying
defect and compare against baseline tools. A scanner finding or self-reported
confidence is not its own ground truth. Ambiguous findings remain unknown and
block the relevant precision/adoption claim until adjudicated. No dead-code
removal is part of the assessment.

## Registered decision gates

Keep issue #75's proposed gates unchanged for this pilot:

- Precision at least 90% per supported language: adjudicated true positives /
  all adjudicated reported positives. Report synthetic and real denominators
  separately; do not hide unknown findings or pool languages to clear a gate.
- Recall at least 80% on the seeded, declared supported defect classes per
  language. Unsupported/incomplete cases remain visible outside that measured
  denominator and cannot support an adoption claim for those features.
- At least three unique useful findings across the six-server suite, after
  baseline-tool overlap and duplicate-defect removal.
- Additional p95 runtime at most 30 seconds. Measure the added scanner wall time
  separately from baseline checks, per language/snapshot and selected mode.
  Use 20 timed runs after one warm-up, report cold-start cost separately, and
  use the nearest-rank 95th percentile. Record host load and artifact reuse.
- All tool registrations remain reachable in the assessment's input/output
  inventory. Any unsupported registration shape is a coverage gap, not proof of
  deadness or an authorization to remove code.

Zero reported positives gives undefined precision, not 100%. A timeout or
incomplete run cannot enter successful latency samples; report it explicitly and
treat that evaluation unit as failing readiness. Any threshold or case-set
revision requires a new preregistration before examining replacement results.

## Failure, suppression, and resumability checks

Before real-snapshot scoring, exercise scanner execution failure, an externally
enforced timeout, missing native engine, malformed/truncated output, unknown
schema, incomplete coverage, unsupported language/feature, and valid/invalid
suppression behavior. Preserve raw exit status and stderr; distinguish a
complete scan reporting findings from an execution failure. Do not use
`--no-fail` or aggregate these states into a clean result.

The runner must key a unit by source snapshot, scanner/dependency hashes,
engine identity, configuration, command, case-set revision, and schema. Publish
a unit only after successful schema/coverage validation. Resume only validated
matching units; interrupted or stale artifacts must not become measurements.
Bound each attempt with an external 120-second deadline and report every timeout
as a failure of that unit. Never average incomplete runs as successes.

## Deliverables and next implementation slice

The next scoped PR should implement the fixture corpus, runner/result schema,
failure-injection cases, and deterministic resume checks. Lock the tool
environment and confirm mode/engine support before running the frozen snapshots.
Subsequent measurement work must publish sanitized raw metrics, per-rule and
per-language coverage/cost, complete finding adjudication, baseline overlap,
and an adopt/adapt/defer/reject decision for **each of the six servers**.

If the evidence supports rollout, propose a MAY/advisory standard with good/bad
fixtures in a later PR. No existing MUST rule is delegated to Skylos by this
protocol. Issue #75 remains open until measured deliverables and decisions are
reviewed; merging this protocol alone does not complete the assessment.
