# Sprint 11 Session 3 Real Part 3 Report

Output: `outputs/sprint11_session_3_20260713_132841`

Source: `LIVE_MT5`

## Observed

- snapshots completed: 120/120
- timed shadow decision: `TIMED_FORWARD_SHADOW_PASS`
- runtime reload: 1 reinitialization / 1 recovery / `runtime_reload_success=true`
- real Part 3 requests: 21
- Part 3 decisions: 21 `APPROVED`
- manual-only Part 3 review results: 21; no broker action
- order actions: 0
- permission leakage: 0
- queue errors: 0
- audit errors: 0
- stage timeouts: 0
- unexplained stalls: 0
- worker invocations: 16

## Candidate and Part 3 Identity

- Candidate instances: 1080
- initial semantic Candidate count: 97
- candidate carry-forward observations: 983
- initial metric showed 480 semantic collisions because its key did not include the stable scenario prefix.
- unique ready Candidates under the initial key: 21
- Part 3 decisions emitted: 21
- repeated ready observations suppressed by idempotency: 132

The initial field named `duplicate_part3_requests=132` was misleading: those were suppressed observations, not emitted duplicate Part 3 decisions. The harness now reports emitted duplicates as `duplicate_part3_requests` and suppression separately as `duplicate_part3_request_suppressions`.

## Unmet Gates

- real reconnect: not exercised (`reconnect_attempts=0`, `reconnect_successes=0`)
- true process stop/resume: not exercised
- corrected semantic lifecycle key: not validated against a new real run

## Decision

`REAL_PART3_PATH_EXERCISED_MANUAL_ONLY`

This is not go-live approval. The next validation must exercise a controlled MT5 disconnect/reconnect and true process resume without duplicate Candidate, Job or Part 3 decision emission.
