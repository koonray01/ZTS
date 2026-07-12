---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: quality_owner
last_updated: 2026-07-12
---

# Sprint 1 MT5 Snapshot Test Matrix

| ID | Test | Class | Expected result | Required evidence |
|---|---|---|---|---|
| S1-001 | MT5 terminal unavailable | Integration | explicit `BLOCKED`; no mock fallback | response + log |
| S1-002 | Symbol unavailable/not selected | Integration | explicit input/runtime error | response + terminal status |
| S1-003 | Pull M5/M15/H1 in one run | Real runtime | same run/snapshot ID and synchronized cutoff | snapshot + manifest |
| S1-004 | Exclude current open candle | Verify | every analytical bar has `is_closed=true` | snapshot + assertion |
| S1-005 | Twenty consecutive snapshots | Real runtime | 20/20 schema-valid with unique IDs | manifests + summary |
| S1-006 | Freshness threshold exceeded | QC | `STALE` and downstream live use blocked | fixture/runtime result |
| S1-007 | Mixed timeframe cutoff | Red team | `MIXED_TIME` or `BLOCKED` | invalid fixture + result |
| S1-008 | Duplicate bars | QC | explicit warning/block per severity | fixture + result |
| S1-009 | Gap detection | QC | gap list emitted; no silent fill | fixture + result |
| S1-010 | Invalid OHLC | QC | schema/check failure and quarantine | fixture + result |
| S1-011 | Broker time/capture time recorded | Verify | valid timestamps and measured age | snapshot |
| S1-012 | Restart/reconnect | Real runtime | reconnect or explicit failure; no stale reuse | logs + snapshots |
| S1-013 | Append-only collision | Security | changed content under same raw path quarantined | manifest + test log |
| S1-014 | Hash verification | Security | altered file detected | test log |
| S1-015 | Account and open positions read-only context | Integration | present or explicitly unavailable | snapshot |
| S1-016 | No order functions exposed | Static/contract | test passes; no public trade-write API | source scan |
| S1-017 | No absolute user path | Static | source/config portable | source scan |
| S1-018 | No cross-system dependency | Boundary | test passes | source scan |
| S1-019 | Terminal/source identity | Verify | terminal/account/source fields traceable | snapshot + manifest |
| S1-020 | Error serialization | Contract | standard response envelope and exit code | CLI test |

## Sprint 1 release requirement
- All synthetic/unit/contract tests pass.
- S1-003, S1-005, S1-011, S1-012, S1-015, and S1-019 are run against a real local MT5 terminal.
- Real runtime evidence must not be simulated or inferred.
