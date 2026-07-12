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
