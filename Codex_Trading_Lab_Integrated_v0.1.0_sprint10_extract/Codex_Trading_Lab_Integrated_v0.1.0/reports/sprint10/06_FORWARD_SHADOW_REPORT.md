# Sprint 10 Forward Shadow Report

Real MT5 status: `TESTED_WITH_REAL_MT5`

Command:

```powershell
python tools/run_forward_shadow.py --output outputs/sprint10_real_forward_shadow_20 --snapshots 20
```

Run timing:

- Start UTC: `2026-07-12T14:53:53.3906460Z`
- End UTC: `2026-07-12T14:54:01.0979932Z`
- Exit code: `0`

Summary:

- Source: `LIVE_MT5`
- Snapshots processed: 20
- Opportunity/scenario count: 60
- Candidate count: 0
- Worker result count: 20
- Duplicate suppression: 0
- Part 3 requests: 0
- Order actions: 0
- Auto execution: false
- Trade write: false
- Evidence raw manifests: 20
- Quarantine records: 0
- Worker job store integrity: true
- Worker result store integrity: true
- Worker audit integrity: true

Decision from run artifact: `GO_FOR_TIMED_REAL_FORWARD_SHADOW`.

Acceptance interpretation: this authorizes timed real forward shadow only. It is not `SPRINT10_FULL_PASS`, `PRODUCTION_READY`, `ENTRY_PIPELINE_VALIDATED`, or `TRADING_EDGE_VALIDATED`.

Updated rapid rerun after worker-dedup fix:

- Source: `LIVE_MT5`
- Snapshots processed: 20
- Unique semantic market-state hashes: 1
- Significant events: 0
- Jobs created: 0
- Jobs suppressed: 0
- Worker invocations: 0
- Duplicate event ratio: 0.0
- Worker invocations per unique state: 0.0
- Candidate count: 0
- Candidate suppression: `SCENARIO_NOT_READY=40`, `SHOCK_BLOCK=20`, all other tracked reasons 0
- Part 3 requests: 0
- Order actions: 0

Important limitation: this was a rapid 20-snapshot capture with interval 0 seconds, not a timed forward shadow session.

## Timed 2-Hour Attempt

Command attempted:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --output outputs/sprint10_real_forward_shadow_2h
```

Result: `TIMED_SHADOW_INTERRUPTED_STALL`

- Requested snapshots: 120
- Raw snapshots observed: 41
- Normalized decisions observed: 41
- Completed requested snapshots: false
- Final forward-shadow report: not written because the process did not complete
- Partial interrupted report: `outputs/sprint10_real_forward_shadow_2h/forward_shadow_partial_interrupted_report.json`
- Partial evidence bundle: `outputs/sprint10_real_forward_shadow_2h/evidence_bundle_partial_interrupted.zip`

Observed stall:

- Snapshot 40 manifest write: `2026-07-12T15:54:16Z`
- Snapshot 41 manifest write: `2026-07-12T18:53:32Z`

This run is not accepted as a timed forward shadow pass. The CLI now has `--max-snapshot-seconds` and returns non-zero if a snapshot stage exceeds the guard or if requested snapshots are not completed.

## CLI Acceptance Status

`tools/run_forward_shadow.py` now separates the harness decision from CLI acceptance:

- `harness_decision`: the raw harness-level decision.
- `acceptance_status`: the acceptance gate result used by the CLI exit code.
- `accepted`: true only when source is `LIVE_MT5`, all requested snapshots complete, at least 20 snapshots are processed, order actions are 0, and no stopped reason exists.

Smoke/probe runs below 20 snapshots return non-zero with `acceptance_status=REAL_MT5_SMOKE_ONLY`.
