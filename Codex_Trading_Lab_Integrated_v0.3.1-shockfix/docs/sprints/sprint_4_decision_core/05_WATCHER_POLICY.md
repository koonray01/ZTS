# Watcher Policy v0.1

Watcher is a deterministic state-diff engine.

Significant events:
- MARKET_STATE_CHANGED
- SHOCK_DETECTED / SHOCK_CLEARED
- ZONE_TOUCHED / ZONE_INVALIDATED
- OPPORTUNITY_STATUS_CHANGED
- SCENARIO_RANK_CHANGED
- SCENARIO_STATUS_CHANGED
- ENTRY_WINDOW_OPENED
- ENTRY_INVALIDATED / ENTRY_EXPIRED

The watcher does not:
- poll MT5 itself in this pack
- call Codex directly
- place or cancel orders
