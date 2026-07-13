# Sprint 11 Candidate Suppression Report

Status: `RUNTIME_VALIDATED_REAL_ENTRY_PATH_PENDING`

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
| `SHOCK_BLOCK` | 120 |
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

Candidate count remained zero, but every snapshot without a Candidate had deterministic suppression reasons. No Entry rule was loosened to force Candidate creation.

Result: `RUNTIME_VALIDATED_REAL_ENTRY_PATH_PENDING`

The runtime and observability path are validated for the no-candidate case. The real Candidate path itself remains pending until a genuine live candidate or clearly labeled real-snapshot replay exercises the downstream mechanics.
