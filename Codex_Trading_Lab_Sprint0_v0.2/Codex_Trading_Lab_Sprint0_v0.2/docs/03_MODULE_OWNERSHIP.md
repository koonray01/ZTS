---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: system_architecture
last_updated: 2026-07-12
---

# Module Ownership

| Module | Owns | Must not own | Public output |
|---|---|---|---|
| `mt5_gateway` | terminal connection, OHLC/tick/account/position evidence, custom buffer/object capture | scenario reasoning, permission | raw capture + connection status |
| `snapshot` | synchronization, immutable snapshot, freshness, closed bars | signals, scenarios | snapshot contract |
| `perception` | facts, features, deterministic events | permission, order placement | sensor outputs |
| `fusion` | coherent market state, conflicts, unknowns, opportunities | execution authorization | compact market packet |
| `scenario` | possible paths, required events, invalidation, expiry, ranking | guaranteed prediction, probability without calibration | scenario tree |
| `entry` | limit/early/full/continuation candidates, RR, latency, missing requirements | final authorization, order placement | entry candidates |
| `safety` | integrity, freshness, provenance, contradictions, hard gates | subjective market interpretation | validation decisions |
| `watcher` | event polling, debounce, deduplication, job triggers | AI reasoning every tick | trigger events |
| `training` | blind replay, scoring, curricula, drills | production policy mutation | training results |
| `knowledge` | episodes, hypotheses, findings, versioned lessons | silent rule promotion | knowledge records |
| `control_plane` | public tools, workflow order, state transitions | detector-specific logic | standardized envelopes |
| `Codex skills` | choose approved workflow, request tools, explain, audit, report | raw writes, checker override, direct order APIs | plans/reports |

## Ownership conflict rule
A module must reject a request that asks it to produce an output owned by another layer. For example, a sensor cannot return `APPROVED` and an entry engine cannot place an order.
