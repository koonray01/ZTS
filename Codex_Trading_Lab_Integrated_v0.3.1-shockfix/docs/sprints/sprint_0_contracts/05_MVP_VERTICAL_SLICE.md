---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: system_architecture
last_updated: 2026-07-12
---

# MVP Vertical Slice

## Scope
- Symbol: XAUUSD
- Timeframes: M5, M15, H1
- Optional context: H4
- Execution: manual only

## Flow
1. Pull one synchronized live snapshot from MT5.
2. Validate connection, freshness, time consistency, bar closure, gaps, and duplicates.
3. Extract candle, swing, and structure features.
4. Detect zones and entry-relevant price-action events.
5. Build a compact market packet.
6. Produce three or more scenario paths.
7. Produce entry candidates:
   - Structured Limit
   - Early Confirmation
   - Full Confirmation
   - Continuation
8. Generate a current action plan.
9. Produce validation report and evidence manifest.

## Required outputs
- `snapshot.json`
- `sensor_results.json`
- `market_packet.json`
- `scenarios.json`
- `entry_candidates.json`
- `current_action_plan.md`
- `validation_report.json`
- `evidence_manifest.json`

## User outcome
The user can either:
- take the plan and watch manually,
- ask the watcher to track a selected plan,
- evaluate a structured limit,
- request permission review for a candidate.

## MVP success condition
The full flow works with real MT5 evidence, remains auditable, and reports opportunity throughput metrics without automatic execution.
