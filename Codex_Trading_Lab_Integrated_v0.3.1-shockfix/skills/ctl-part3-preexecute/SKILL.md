---
name: ctl-part3-preexecute
description: Use when the user explicitly requests deterministic Part 3 review for a currently eligible READY_FOR_PERMISSION_REVIEW Candidate.
---

# Part 3 Preexecute

Part 3 is a separate primary route. `ctl-market-analysis-registry` may identify the trigger but must not invoke this skill automatically.

## Preconditions

Require explicit intent, a still-valid `READY_FOR_PERMISSION_REVIEW` Candidate, matching snapshot/evidence bindings, freshness, expiry, locks, and zero-write safety flags. Otherwise return the deterministic blocker.

## Output

Run and explain each deterministic gate. Return exactly `APPROVED`, `WAIT`, `REJECTED`, or `INVALIDATED`, with blockers, evidence references, snapshot/Candidate/decision IDs, expiry, and invalidation.

`APPROVED` means Manual Review Only and authorizes no order action.

## Boundaries

Do not invent eligibility, convert UNKNOWN into PASS, override FAIL/BLOCK, modify deterministic output, mutate evidence or policy, or place, change, cancel, or close broker orders.
