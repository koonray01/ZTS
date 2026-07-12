---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: schema_owner
last_updated: 2026-07-12
---

# Schema Field Guide

## Common identifiers
- `run_id`: one control-plane workflow execution.
- `snapshot_id`: one immutable synchronized market-state input.
- `evidence_id`: one evidence object or manifest entry.
- `packet_id`: one derived packet.
- `scenario_id`: one possible market path.
- `candidate_id`: one possible entry plan.

## Claim classes
- `FACT`: directly read from source evidence.
- `DERIVED`: deterministic calculation with declared inputs/checker.
- `INTERPRETATION`: higher-level reading; cannot grant permission.
- `UNKNOWN`: unavailable or unresolved information.

## Time semantics
- All transport timestamps use ISO 8601.
- UTC timestamps end in `Z`.
- Broker time records its UTC offset separately when not UTC.
- Analytical bars are closed bars only.

## Numeric price semantics
Prices use JSON numbers in the contract. Runtime code must preserve broker digits and avoid formatting-based comparison.

## Qualitative ranking
Initial scenario ranking is `PRIMARY`, `SECONDARY`, `LOWER_PRIORITY`, or `TAIL_RISK`. Numeric probability is intentionally absent until a calibrated schema version is approved.
