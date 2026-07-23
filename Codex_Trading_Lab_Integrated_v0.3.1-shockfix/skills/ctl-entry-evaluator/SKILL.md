---
name: ctl-entry-evaluator
description: Use when the primary market-analysis workflow needs deterministic Candidate listing, comparison, or classification without creating a signal or granting trading permission.
---

# Entry Evaluator

For current/live analysis, operate as a supporting step inside `ctl-market-analysis-registry`. Use its bound snapshot. Do not capture another snapshot. Do not duplicate Registry writes.

## Inputs

- Deterministic Candidate records and evidence bindings
- Current lifecycle, expiry, invalidation, and blockers

## Output

Return only still-valid Candidates with IDs, scenario, side, entry type/range, stop, targets, RR, missing conditions, latency, lifecycle, expiry, invalidation, and limit eligibility. Distinguish `ZENITH_CANDIDATE`, `CONDITIONAL_WATCH_SETUP`, and `NO_SETUP` exactly.

## Boundaries

Never synthesize a Candidate from narrative, relabel a Chat setup as Zenith, or alter frozen four-tier geometry retrospectively. Do not capture another snapshot. Do not duplicate Registry writes. Never infer UNKNOWN as PASS, override deterministic eligibility, grant Permission, mutate evidence/policy, or write to broker state.
