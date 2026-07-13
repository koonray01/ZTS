# Part 3 Policy v0.1

## Gate order
1. Identity and contract
2. Snapshot freshness and QC
3. Candidate lifecycle
4. Evidence and dependency integrity
5. Trigger/setup readiness
6. Market safety
7. RR and invalidation
8. Account and risk budget
9. Duplicate/idempotency

## Decision semantics
- APPROVED: all mandatory gates pass; manual execution only
- WAIT: recoverable missing condition or fresh snapshot required
- REJECTED: candidate is currently unacceptable but not structurally dead
- INVALIDATED: candidate/setup identity, expiry or structural basis is dead

## Hard rule
Scenario rank, LIMIT_READY, AI confidence and sensor agreement are not permission.
