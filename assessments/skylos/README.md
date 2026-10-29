# Optional Skylos pilot runner

This module implements the synthetic-input slice of
[issue #75](https://github.com/millsmillsymills/consistency-check/issues/75), under
the [preregistered protocol](../../docs/assessments/skylos/README.md).
It is separate from the installed compliance auditor and its mandatory rules.

## Frozen inputs and toolchain

`corpus.json` revision 1 contains 15 defects and 15 benign controls per language,
covering Python and Go. Case source, ground truth, requested mode, and expected
family are registered together. Duplicate source inputs, unbalanced counts, unsafe
paths, existing destination directories, links, and post-materialization changes
are rejected. Python examples were parsed and 36 Go files were checked with
`gofmt`; corpus programs are never executed by this runner.
Each unit has its own fixed-date Git commit and scanner working directory, so
parent-repository references/history cannot leak into a scan. Its marker contains
hashes rather than copied source or truth labels; marker text cannot rescue a
dead symbol by mentioning its code. Only the synthetic Git repository is created;
no Git hooks run and no owner checkout is modified.

`requirements.lock` records exact versions and artifact hashes for Skylos 5.1.5
and all 68 packages in its isolated environment. The macOS arm64 identity profile
records the selected wheel URLs/hashes, installed distribution payload hashes,
Python/host identity, dependency-lock hash, launcher hash, and native-engine hash.
Wheel downloads were matched to installed WHEEL tags and their SHA-256 values
checked against both PyPI metadata and the lock before recording the profile.
No package or engine is installed globally.

The wheel's bundled engine prints `skylos-go dev`. That string alone is not
release provenance. For this profile the engine was built independently from
the clean pinned upstream commit `4f32409b5aaf913ca249483dc15221118c6c56db`
with Go 1.26.2, `-trimpath -buildvcs=false`, and `GOPROXY=off; GOSUMDB=off`.
The source uses a constant `dev` standalone version; its exact build hash and
source revision, rather than that label, identify the measured engine.

To recreate the isolated package installation:

```sh
uv venv .scratch/skylos-env
uv pip sync --python .scratch/skylos-env/bin/python --require-hashes \
  --only-binary :all: assessments/skylos/requirements.lock
```

The checked-in identity is host/install specific, including generated launchers.
Another host or installation path must capture and review a fresh identity from
the locked artifacts before measuring. Do not edit expected hashes merely to
bypass a mismatch. Installed payloads and the selected scanner/engine are checked
before use; profile or source changes invalidate resume keys.

## Collect observations

```sh
uv run python -m assessments.skylos --case python-01-defect --sample 0
uv run python -m assessments.skylos --sample 0
```

Outputs default to ignored `audit-out/skylos/`: inputs and evidence are kept in
separate directories. Only registered synthetic inputs with matching markers
are accepted; this CLI does not scan owner-server checkouts or make service calls.
It never runs corpus code, tests, build scripts, tracing, cleanup, hooks, cloud,
or model modes. Static scan modes force `--no-upload` and a trusted empty config;
workspace verification disables dependency lookups, behavior execution/comparison,
and contract discovery. Child processes do not inherit API credentials and Go
package-network access is disabled. These controls are not a general OS network
sandbox; no real-snapshot measurement is authorized by a synthetic result alone.

Sample 0 is a warm-up/characterization observation. Distinct `--sample` values
identify the preregistered timed repetitions; this slice does not compute p95,
precision, recall, or an adoption verdict. `valid_measurement` means structurally
complete scanner evidence, including a complete scan that reports findings. It
does not mean the scanner passed the pilot's quality or rollout criteria.
Unsupported/incomplete analysis remains nonpassing and requires adjudication.

## Raw evidence, contracts, and resume

Each attempt has its own directory containing raw `stdout.bin`, `stderr.bin`,
and `result.json`, with return code, elapsed time, source/case/environment hashes,
and normalized coverage/findings. A deadline terminates the entire POSIX process
group, including a native engine. Execution failures, timeouts, malformed output,
unknown schemas, incomplete coverage, and input mutation retain artifacts and
never produce a reusable completion receipt. Rejected prior receipts are retained
with the replacement attempt.

The adapters bind to upstream 5.1.5: verify schema 2 and coverage schema 1, plus
the explicitly **unversioned** static-result shape of that release. Missing
requested language/check coverage and missing Go engine phases are not passes.
Suppressed findings remain visible instead of becoming unreported true negatives.
Unknown/malformed suppression output is rejected.

Resume keys bind source files, complete case metadata, command/configuration,
toolchain identity, timeout, sample, and adapter source hashes. Reuse checks the
receipt and every result/stdout/stderr digest and revalidates the output contract.
Stale or corrupt attempts are retained, not silently counted or overwritten.

The runner intentionally supplies no automatic ground-truth scoring. A matching
rule family is only candidate evidence; a reviewer must adjudicate incidental,
duplicate, unsupported, suppressed, and unknown findings before calculating any
pilot gate. Real-snapshot inventories, baseline-tool comparisons, independent
finding adjudication, suppression characterization, and all six rollout decisions
remain later measured work under #75.
