# Natural-Language Trading Assistant Skills

This file defines the operational skills exposed through ordinary user language. The assistant performs the underlying read-only system calls itself; users should not need to type PowerShell commands.

## Core skills

- `start_live_session`: XAUUSD, Manual Only; validate MT5, LIVE_MT5 source, freshness, QC, session state, locks, and disabled write/execution flags; read M5/M15/H1/H4.
- `read_market`: produce FACT / INTERPRETATION / UNKNOWN market summary with structure, regime, volatility, zones, liquidity, scenarios, waits, prohibitions, and candidate status.
- `check_candidates`: return only valid current candidates and all required fields; never synthesize a signal.
- `build_action_plan`: produce HOLD/WATCH/READY_FOR_PERMISSION_REVIEW with explicit wait, cancel, invalidation, and Part 3 trigger conditions.
- `run_part3_manual_review`: deterministic gates only; allowed only for READY_FOR_PERMISSION_REVIEW; APPROVED is manual review, never execution.
- `build_manual_proposal`: allowed only after latest Part 3 APPROVED; proposal is informational and never sent to MT5.
- `update_market`: compare fresh snapshots and report deltas or `NO_SIGNIFICANT_CHANGE`.
- `record_manual_entry`: record user-provided entry metadata without writing to broker state.
- `monitor_position_read_only`: inspect position and return HOLD/PROTECT/REDUCE_REVIEW/EXIT_REVIEW/MANUAL_RECONCILIATION_REQUIRED; no SL/TP/order writes.
- `end_session`: close audit, assert zero order actions and zero permission leakage, verify evidence integrity, and build evidence bundle.

## Safety invariants

1. Manual Only is permanent for this workflow.
2. `trade_write_enabled=false` and `auto_execution_enabled=false` are mandatory.
3. No broker order placement, modification, cancellation, or close.
4. No Part 3 before a valid READY_FOR_PERMISSION_REVIEW candidate.
5. Opportunity is not Permission.
6. UNKNOWN remains UNKNOWN; deterministic FAIL/BLOCK cannot be overridden.
7. Every claim is bound to a fresh LIVE_MT5 snapshot and evidence references.
8. Position tracking is read-only.

## Response shape

Every market response should identify: symbol, snapshot ID/time, source, freshness/QC, session safety flags, then sections `FACT`, `INTERPRETATION`, `UNKNOWN`, `ACTION`, and `EVIDENCE`. Candidate and Part 3 reports must include lifecycle, expiry, invalidation, and binding IDs.
