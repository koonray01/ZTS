---
name: ctl-live-event-review
description: Use when the user explicitly requests read-only position monitoring or review of a significant live watcher event.
---

# Live Event Review

This is the primary route only for monitoring/event-review intent. Delegate ordinary current-market analysis and updates to `ctl-market-analysis-registry`.

## Inputs

- Current validated state and significant event
- Bound position/Candidate IDs and evidence references

## Output

Explain what changed, impact, invalidation or expiry effects, and the next manual-review action. Position review returns one of `HOLD`, `PROTECT`, `REDUCE_REVIEW`, `EXIT_REVIEW`, or `MANUAL_RECONCILIATION_REQUIRED`. State whether a fresh explicit Part 3 review may be warranted; do not run it automatically.

## Boundaries

Read only. Never place, modify, cancel, close, reconcile, or alter SL/TP in MT5. Do not restart the market orchestration flow, duplicate Registry writes, override deterministic results, or grant permission.
