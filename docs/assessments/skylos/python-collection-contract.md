# Proposed Python-only collection contract

Status: design for independent review, 2026-11-05. No collection authorization or implementation. Related: consistency-check #75, #92 and merged #94. Preserve all frozen cases, classifications, historical receipts and Go deferral.

## Separate entry point and prerequisites

Keep the existing schema-1 collector unchanged. Schema-2 `python-identity-preflight` remains metadata-only with `collection_authorized=false`; neither changing that boolean nor passing preflight enables collection.

Implement a separate Python synthetic collector only after this contract is reviewed. Its first scope is the registered Python synthetic corpus, not real server snapshots, runtime registration, baseline tests or live services. Reject Go cases, arbitrary directories, unknown modes, missing prerequisites and mixed-language selections before launching a child. A later real-snapshot protocol needs its own source-selection, coverage, configuration and authorization review.

Require a distinct reviewed collection manifest with schema 3 and purpose `python-synthetic-collection`, explicit `go_evaluation=deferred`, the schema-2 identity digest, exact frozen corpus digest, pinned scanner source/lock/payload identity and an immutable review/authorization reference specifying allowed cases, modes, sample range and resource limits. Schema numbers are proposed for this entry point, not permission to widen existing parsers. Verify current metadata and file hashes again immediately before execution. An authorization field is an auditable reference to an actual decision, not self-authorization by configuration.

The manifest must enumerate the expected Python input files with byte hashes and independently selected mode/check IDs before launch. Validate reported coverage against that external expectation, not merely the scanner output's own `expected_checks` list. Characterize any pinned mode lacking adequate file/check attribution as unsupported or incomplete until a reviewed coverage proof exists.

## Observation and cache identity

Use a new namespace `python-synthetic-v1` and separate store; never adopt old completion receipts. The key binds namespace, collection manifest and approval reference, preflight identity, interpreter/host/package/launcher hashes, scanner source/lock, complete case metadata and source bytes, requested language/checks, sample and repetition plan, command and trusted configuration, adapter/collector/corpus/environment source hashes, timeout and output limits, and isolation/environment policy. Hash canonical JSON plus exact file bytes with SHA-256; reject duplicate JSON keys and nonfinite numbers. Include adapter revision as well as source hash.

The interpreter binary hash is a proposed new field: existing schema-2 preflight records Python version/host metadata, distribution payloads and launcher hashes, not the interpreter executable hash. Capture the resolved executable and relevant runtime identity, then implement explicit verification before claiming those fields are bound to observations.

Sample 0 remains characterization. No historical attempt is relabeled as the new host's observation. Any implementation, environment, scope, limits or protocol change invalidates reuse. Paths that influence scanner behavior must be included or normalized by a reviewed deterministic mapping; do not silently remove existing command/path identity inputs.

Each attempt gets an immutable unique directory and start manifest before launch. Retain bounded raw stdout/stderr, exit status or signal, duration, input hashes before/after, coverage, findings (including suppression), parser version and explicit terminal state. Atomic completion receipts are written last, only after artifacts and validation finish. Crashes/partial writes never become reusable receipts; preserve rejected/corrupt prior receipts and retry in a new directory. Reuse requires rehashing all artifacts, recomputing the key and revalidating output. Enforce one writer per key or explicitly implement concurrency-safe receipt publication.

## Failure and coverage contract

Terminal states distinguish preflight rejection, spawn error, timeout, output-limit termination, invalid output/schema, incomplete coverage, changed input, interrupted/partial persistence and structurally complete output. None except structurally complete output can receive a completion receipt. Findings alone are not execution failures; acceptance of an exit code remains bound to the pinned adapter and requested mode. Retain failure reasons without converting missing data to empty results.

Preserve pinned static-result and verify schema contracts, exact requested Python/check coverage, counts and suppressions. Unknown schema, missing requested coverage, inconsistent counts, unreadable/skipped requested inputs and null-versus-empty ambiguity fail closed. An explicit zero-input out-of-scope skip is distinct from requested-input coverage. An empty findings list is not evidence of analyzed input or framework support. Structural completeness confers neither truth labels, denominator eligibility, precision/recall nor adoption. Preserve cases 06–08/13 as unmeasured for the disputed capability, case 14-defect as incomplete, and all outstanding policy-advice judgments.

Before implementation approval, specify finite byte limits separately for stdout and stderr, a total artifact limit and enforcement strategy. Stream capture with limits; `communicate()` followed by truncation is not a memory bound. Terminate and reap the whole process group on timeout or overflow, including descendants; retain allowed partial bytes and explicit truncation flags. Resource limits become part of the reviewed manifest and key. Do not derive favorable limits after observing results.

## Isolation and Go deferral

Use disposable, verified synthetic Git roots with hooks disabled, trusted empty scanner config, a credential-free environment and isolated HOME/config/cache/temp locations. Preserve no upload/model/clipboard/provenance/behavior/contract/dependency-lookup settings for the applicable mode. Do not import or execute corpus programs. Credential stripping and scanner flags are not a network sandbox: require and fixture-test an enforceable no-network/no-device execution boundary before collection.

Do not manufacture a Go engine identity or normalize native `refs:null`. The new Python path must neither verify nor invoke a Go engine. Merely omitting `SKYLOS_GO_BIN` is insufficient because bundled/PATH discovery may remain possible. Review the pinned scanner's dispatch and enforce/test denied Go-engine execution, including Python verify mode; defer any mode whose independence cannot be demonstrated. A failure is retained as unsupported/incomplete, not treated as zero references.

## Required implementation validation

Use deterministic stub executables and fixture outputs, not scanner measurements, to test schema separation; rejection before spawn; identity drift; Go/mixed/arbitrary-root rejection; missing/partial/unknown coverage; null/empty and count inconsistencies; suppression visibility; supported finding exit codes; malformed JSON; timeout/descendant cleanup; stream overflow; spawn failure; interruption and atomic persistence; input mutation; corrupt/missing artifacts; concurrent same-key behavior; no-network/device and Go-engine denial. Assert that each identity component changes the key, old namespaces never resume, and incomplete attempts cannot create completion receipts. Tests must show actual boundaries rather than merely repeat implementation conditionals.

Independent review of the exact signed implementation head, relevant full suite and CI, and a separately recorded scoped collection decision are still required. This document does not resolve scanner applicability, semantic judgments, baseline overlap, timing or six repository rollout decisions.

## Frozen baseline compatibility assessment

Read-only Git-object inspection of `pyproject.toml`, `uv.lock` and CI at the five commits in `docs/assessments/skylos/snapshots.json`; no installation, resolver, baseline command or target import ran. Python 3.13.9 satisfies all five project and lock floors (`>=3.13`). This is declared compatibility only; the original workflows use Ubuntu, whereas the new candidate is macOS arm64.

| Frozen repository | Ruff | ty | MCP | Lock package records | Scope from CI |
| --- | --- | --- | --- | --- | --- |
| unraid-mcp | 0.15.22 | 0.0.61 | 1.28.1 | 124 | Ruff src/tests; ty src/unraid_mcp |
| unifi-mcp | 0.17.1 | 0.0.89 | 2.3.0 | 110 | Ruff and ty src/tests |
| gandi-mcp | 0.15.22 | 0.0.61 | 1.28.1 | 127 | Ruff src/tests; ty src/gandi_mcp; Bandit |
| shortcut-mcp | 0.15.15 | 0.0.42 | 1.28.1 | 95 | Ruff repository root; ty configured defaults |
| flipperzero-mcp | 0.15.22 | 0.0.61 | 1.28.1 | 116 | Ruff src/tests; ty src/flipperzero_mcp; Bandit |

Counts include alternative-resolution packages, not a promised installed set. Every registry package has wheel records, but applicable marker branches, macOS/Python tags, artifact availability and hashes still require selection and verification. The only nonregistry source in each lock is its editable root project. Every root uses unversioned `hatchling` in build-system requirements: a frozen application lock alone does not prove a reproducible isolated build-backend environment. Record and review exact build requirements/artifacts before allowing project build hooks, or separately preregister a no-build baseline with explicit import-resolution limitations; never quietly substitute it for the original baseline.

All CI installs select the `dev` extra; Flipper also declares a `dev` dependency group. Preserve both applicable selections and record platform markers. Do not merge these environments with the 68-package scanner environment or with each other. Use disposable frozen source exports, separate environments/cache/output namespaces, locked artifact selection without lock rewriting, and before/after hashes. An installation failure remains a compatibility blocker; do not upgrade pins to obtain a pass.

Ruff/ty results depend on each frozen config and scope: Unraid ignores unresolved imports, UniFi has test overrides, and Flipper excludes generated protobuf analysis through explicit configuration. Retain these differences in any overlap interpretation. Gandi and Flipper also run Bandit; that baseline must not be omitted by treating Ruff/ty as the complete suite.

Pytest, package build hooks, catalog generators, cassette refreshes and startup code execute project code. They are outside this preparation and require separate fixture/network/device review before any approved baseline run. In particular, Gandi cassette refresh targets may record traffic; UniFi defaults do not globally exclude all integration tests; Flipper integration requires hardware. Test markers alone are not isolation proof. No blanket CI or Make target execution is proposed.

Next compatibility gate: derive and independently review each platform-selected artifact set and build-backend identity from frozen inputs; then approve isolated installation and exact static commands separately. Keep test/baseline execution and all new scanner observations pending that readiness review.
