# Scenario and Entry Policy v0.1

## Scenario
- PRIMARY
- SECONDARY
- LOWER_PRIORITY
- TAIL_RISK

No probabilities until calibrated.

## Entry types
- STRUCTURED_LIMIT
- EARLY_CONFIRMATION
- FULL_CONFIRMATION
- CONTINUATION

## Hard requirements
- fresh/QC-passed data
- valid location
- structural invalidation
- positive risk distance
- minimum RR
- no blocking shock/conflict

## Quality enhancers
- higher-timeframe alignment
- liquidity alignment
- FVG
- order-block candidate
- dealing-range location

Enhancers may change context or future risk sizing, but do not silently become hard gates.
