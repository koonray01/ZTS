---
name: ctl-market-read
description: Use when the active workflow needs a deterministic, snapshot-bound Zenith market interpretation without creating scenarios, Candidates, or permission.
---

# Market Read

For current/live user requests, delegate the primary flow to `ctl-market-analysis-registry`. Consume its already-bound fresh snapshot; do not capture another snapshot or write a second Registry record.

## Inputs

- Validated snapshot ID, timestamp, source, freshness, and QC
- Deterministic state and evidence references

## Output

Report timeframe structure, regime, volatility/shock, zones, liquidity, conflicts, changes, and unknowns. Separate `FACT`, `INTERPRETATION`, and `UNKNOWN`; bind claims to evidence.

## Boundaries

Do not invent market facts, scenarios, Candidates, or permission. Do not alter evidence, deterministic outputs, policy, broker state, or skill versions.
