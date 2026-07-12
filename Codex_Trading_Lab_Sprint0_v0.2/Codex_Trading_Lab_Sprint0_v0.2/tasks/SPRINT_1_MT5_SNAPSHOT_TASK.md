---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: implementation_owner
last_updated: 2026-07-12
---

# Sprint 1 Task — Fresh MT5 Snapshot

## Objective
Implement a standalone, read-only MT5 snapshot service for XAUUSD that produces immutable schema-valid M5/M15/H1 snapshots with explicit freshness and QC.

## Inputs
- local Windows MT5 terminal,
- XAUUSD symbol name/configuration,
- Python MetaTrader5 package or approved local bridge,
- `schemas/snapshot.schema.json`,
- public tool/CLI contract,
- evidence append-only policy,
- Sprint 1 test matrix.

## Required implementation
1. Python package/CLI skeleton.
2. MT5 connection adapter with explicit terminal/source identity.
3. Symbol selection and metadata check.
4. Closed-bar retrieval for M5, M15, H1; optional H4.
5. Snapshot synchronization and cutoff calculation.
6. Freshness calculation.
7. Gap, duplicate, OHLC, count, and mixed-time QC.
8. Read-only account/position context.
9. Immutable raw evidence + manifest + normalized snapshot.
10. Standard response envelope and exit codes.
11. Latest snapshot pointer written atomically.
12. Tests and run reports.

## Required output path
```text
outputs/snapshot/<run_id>/
├── response.json
├── snapshot.json
├── validation_report.json
├── evidence_manifest.json
└── run.log
```

## Acceptance evidence
- unit and integration test report,
- 20 consecutive real MT5 snapshots,
- reconnect test,
- stale/mixed/gap/duplicate/invalid-OHLC tests,
- append-only/hash tests,
- static proof that no order-write API is exposed,
- known gaps.

## Forbidden
- any live order placement/modification/cancellation,
- silent fallback to fixture/mock,
- imports or reads from the existing TradingOS main system,
- advanced perception/SMC/ICT logic,
- claiming real runtime success before evidence is produced.

## Sprint 1 exit decision
`PASS`, `CONDITIONAL_PASS`, `FAIL`, or `QUARANTINE` based on the test matrix.
