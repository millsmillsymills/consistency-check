# Capability and suppression characterization

Issue #75, phase after runner PR #88. Registered before collecting observations.
The scored corpus remains revision 1, SHA-256
`93233d48104537eb6cb999dd1e53381392e98d5867188c6b25b2ff66aa9c58ef`.
The verified environment identity is
`6b12b155131cc4274a27d4de86d6ceae13318fef8219989bb5f7afea09e119ca`.

`assessments/skylos/characterization-plan.json` freezes seven extra suppression
probes, separate from the 60 scored cases. Python probes compare an unsafe
`eval(input())` with no marker, a rule-specific `SKY-D201` ignore, the unsupported
legacy `skylos-ignore` spelling, and a valid marker for the wrong rule. The pinned
source's `config.py` and `analysis/finding_filter.py` predict that only the
rule-specific marker suppresses this finding. The source text is never executed.
Go probes compare an unused private function with no marker and the two marker
spellings. Go inline suppression support is not established; characterize the
observed behavior without assuming the Python policy applies.

Capture pinned CLI/verify help, JSON doctor output with
`SKYLOS_HOOKS_DISABLE=all`, source-built engine version, exact environment/input
hashes and raw outputs under ignored `audit-out/skylos/characterization/`.
Disabling hook self-tests prevents doctor from running global hook commands.
Use the runner's restricted environment, disposable Git inputs and process-group
deadline. The selected native engine must be available and match its hash before
any Go observation. Help must confirm all registered static/verify flags.

Use corpus cases 01, 06, 09 and 15 for each language to characterize dead-code,
workspace proof, security and quality coverage. Retain failures, malformed
outputs, unsupported phases and incomplete checks as nonpassing. Do not edit
case source or expected classifications in response to scanner outcomes.

After the preflight and suppression behavior are understood, collect sample 0
for all 60 frozen cases. This is warm-up/capability evidence, not the registered
20 timed repetitions and not a latency or adoption claim. Complete matching
sample-0 units may resume. A changed adapter must create new observations while
preserving rejected attempts. Unsupported or ambiguous cases require explicit
adjudication before any recall denominator is formed.

No real server snapshot is scanned in this phase. Representative-role inventories,
baseline-tool verification, independent real-finding adjudication, 20 timed runs,
suite overlap and all six rollout decisions remain prerequisites for later work.
