# Fusion Policy v0.1

## Ownership
- Structure: Basic Structure sensor
- Trend context: Trend sensor
- Range/transition: Range sensor
- Volatility: Volatility/Shock sensor
- Zones: Advanced zone sensors
- Liquidity: Liquidity sensor
- Events: deterministic event outputs

## Conflict policy
Conflicts are surfaced, not averaged away.

Examples:
- H1 bullish vs M5 bearish → non-blocking timeframe conflict
- Shock vs normal entry logic → blocking risk flag
- Unknown structure → retained as UNKNOWN

## Opportunity policy
Opportunity is broader than permission:
- Zone/location can create WATCH
- Sweep can create ARMED
- Reclaim/Break can create READY_FOR_ENTRY_EVALUATION
- None of these grant permission
