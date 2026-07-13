# MVP Vertical Slice

## Scope
Symbol: XAUUSD
Timeframes: M5, M15, H1
Execution: manual only

## Flow
1. Pull one synchronized live snapshot from MT5.
2. Validate freshness and closed bars.
3. Extract candle, swing, and structure features.
4. Detect current zones and price-action events.
5. Build compact market packet.
6. Produce three scenario paths.
7. Produce entry candidates:
   - Structured Limit
   - Early Confirmation
   - Full Confirmation
   - Continuation
8. Generate current action plan.
9. Produce validation and evidence manifest.

## Required outputs
- snapshot.json
- sensor_results.json
- market_packet.json
- scenarios.json
- entry_candidates.json
- current_action_plan.md
- validation_report.json
- evidence_manifest.json
