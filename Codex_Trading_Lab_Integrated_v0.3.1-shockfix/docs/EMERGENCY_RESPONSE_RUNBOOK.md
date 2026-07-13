# Emergency Response Runbook

Status: `DRAFT`

Use this when runtime stability, evidence integrity or permission integrity is uncertain.

## Immediate Pause Conditions

Pause and stop relying on new output if any of these occur:

- `order_actions > 0`
- trade-write flag is unexpectedly enabled
- auto-execution flag is unexpectedly enabled
- permission leakage detected
- stage timeout
- unexplained stall
- hash mismatch
- evidence collision not quarantined
- terminal identity changes unexpectedly
- account identity changes unexpectedly
- snapshot source changes unexpectedly

## Emergency Lock Conditions

Lock the session for human review if:

- a Worker fabricates `APPROVED`
- Part 3 identity mismatches the current snapshot
- candidate expiry is uncertain
- shock state is active and policy is unclear
- diagnostics heartbeat stops moving
- output path was reused accidentally

## Response Steps

1. Do not place or modify any broker order from system output.
2. Stop the current command if it is still running.
3. Preserve the output directory.
4. Bundle evidence if the evidence tree is readable.
5. Record the latest diagnostics file.
6. Record the latest stdout/stderr.
7. Mark the run not accepted.
8. Start the next run only with a fresh output directory.

## Evidence Bundle

```powershell
python tools/bundle_sprint10_evidence.py --evidence-root outputs/<run>/evidence --output outputs/<run>/evidence_bundle.zip
```

## Safety Rule

No emergency procedure may weaken deterministic safety guards or convert UNKNOWN into PASS.
