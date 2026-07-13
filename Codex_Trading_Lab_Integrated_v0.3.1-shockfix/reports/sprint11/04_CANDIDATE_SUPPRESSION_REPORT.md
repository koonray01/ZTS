# Sprint 11 Candidate Suppression Report

Status: `REAL_CANDIDATE_OBSERVED_PART3_PENDING`

Scope: `outputs/sprint11_real_forward_shadow_2h`

## Metrics

- snapshots_without_candidate: 120
- snapshots_with_candidate: 0
- candidate_count: 0
- opportunities_created: 0
- scenarios_created: 360
- ready_scenarios: 0
- candidates_created_by_entry_type: none
- candidates_rejected_by_gate: none
- average_candidate_lifetime: not applicable
- candidate_expiry_count: 0
- suppression_explained_ratio: 100%

## Suppression Counts By Reason

| Reason | Count |
|---|---:|
| `NO_OPPORTUNITY` | 120 |
| `SCENARIO_NOT_READY` | 240 |
| `SHOCK_BLOCK` | 120 from old observability logic, not confirmed actual shock |
| `NO_VALID_LOCATION` | 0 |
| `NO_ACTIVE_ZONE` | 0 |
| `TRIGGER_PENDING` | 0 |
| `RR_BELOW_MINIMUM` | 0 |
| `CONFLICT_BLOCK` | 0 |
| `SNAPSHOT_QC_BLOCK` | 0 |
| `STALE_DATA_BLOCK` | 0 |
| `REQUIRED_INPUT_UNKNOWN` | 0 |
| `LIMIT_NOT_ELIGIBLE` | 0 |
| `ENTRY_EXPIRED` | 0 |
| `STRUCTURE_NOT_CONFIRMED` | 0 |
| `SETUP_FAMILY_NOT_READY` | 0 |
| `POLICY_BLOCK` | 0 |
| `OTHER_EXPLICIT_REASON` | 0 |

## Interpretation

Candidate count remained zero, but shock audit changed the interpretation of the old suppression breakdown.

Updated interpretation after `reports/sprint11/10_SHOCK_DETECTOR_AUDIT.md`:

- actual shock active snapshots: 0
- volatility states: `UNKNOWN` across M5/M15/H1/H4
- Basic Eyes block reason: `SNAPSHOT_NOT_FRESH`
- old `SHOCK_BLOCK` count was caused by tail-risk scenario classification, not confirmed shock risk flags

Future runs now report `primary_suppression_reason`, `secondary_suppression_reasons`, and a candidate funnel. No Entry rule was loosened to force Candidate creation.

Result: `RUNTIME_VALIDATED_REAL_ENTRY_PATH_PENDING_WITH_FRESHNESS_AUDIT_REQUIRED`

The runtime and observability path are validated for the no-candidate case. The real Candidate path itself remains pending until a genuine live candidate or clearly labeled real-snapshot replay exercises the downstream mechanics.

## Freshness Fix Canary

After timestamp normalization and session-gap handling:

- output: `outputs/sprint11_freshness_fix_canary_20260713_102820`
- snapshots: 10
- valid_locations: 10
- active_zones: 380
- opportunities: 30
- scenarios: 50
- ready_scenarios: 0
- entry_candidates: 90
- watcher_events: 2
- jobs_created: 1
- part3_requests: 0
- primary_suppression_reason: `TRIGGER_PENDING=10`

This is real-market-origin Candidate creation, but not a complete Real Candidate -> Part 3 path.

## Session 2 Timed Shadow

Output: `outputs/sprint11_session_2_20260713_104017`

Funnel:

```text
snapshots:         120
valid_locations:   120
active_zones:     4009
opportunities:     390
scenarios:         600
ready_scenarios:     0
entry_candidates: 1080
watcher_events:     26
part3_requests:      0
```

Suppression:

- primary `SCENARIO_NOT_READY`: 115
- primary `SHOCK_BLOCK`: 5
- secondary `TRIGGER_PENDING`: 120
- secondary `CONFLICT_BLOCK`: 95
- secondary `SCENARIO_NOT_READY`: 5

Candidate creation is validated with real MT5 origin. Full Part 3 path remains pending.
