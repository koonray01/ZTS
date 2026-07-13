# Sprint 11 Candidate Lifecycle and Session 3 Plan

Status: `READY_FOR_REAL_SESSION_3`

Session 2 proved real-market-origin Candidate creation, but its 1080 Candidate instances were snapshot-scoped. It cannot by itself distinguish new Candidates from carry-forward instances.

The Session 3 harness records:

- `unique_candidate_ids`
- `new_candidates_created`
- `candidates_carried_forward`
- `candidate_status_changes`
- `candidates_expired`
- `candidates_invalidated`
- `duplicate_semantic_candidates`
- `part3_eligible_candidates`
- `part3_blocked_by_gate`
- `part3_not_requested_reason`

Candidate identity used for lifecycle analysis is semantic and does not replace the snapshot-bound `candidate_id` required by the existing contract and Part 3 evidence identity.

Part 3 is called once for a semantic Candidate only after it is `READY_FOR_PERMISSION_REVIEW`. All other Candidate states are reported as suppressed, not silently ignored. `APPROVED` remains a manual-review result and cannot place, modify or cancel an order.

Session 3 procedure:

1. Run 120 snapshots at 60-second cadence with `--restart-after-snapshot 40`.
2. During the session, perform one operator-controlled MT5 connectivity interruption and restoration. The harness may retry one transient unavailable capture and records both attempt and success.
3. Bundle evidence only after the report confirms zero order actions, zero permission leakage and zero unexplained integrity errors.

Acceptance is not a Candidate-count target. A zero Part 3 request is acceptable only when `part3_not_requested_reason` accounts for every Candidate instance and no eligible Candidate was silently skipped.
