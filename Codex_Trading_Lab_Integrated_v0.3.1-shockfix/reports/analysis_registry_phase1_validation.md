# Analysis Performance Registry Phase 1 Validation

**Date:** 2026-07-20

**Branch:** `feature/analysis-performance-registry-phase1`

**Implementation commits:** `331d52e`, `645c1cd`, `7538390`, `ff5e14a`, `d02ddd5`

## Scope

Phase 1 covers deterministic identities, event and bundle schemas, hash-chained
append-only JSONL storage, read-only Zenith ingestion, rebuildable SQLite
projections, fail-closed verification, and evidence documentation. Outcome
labeling, performance metrics, External/Comparison ingestion, historical
migration, dashboards, and upgrade gates remain Phase 2+ work.

## Focused registry tests

Command:

```text
$env:PYTHONPATH="src"; python -m pytest tests/test_analysis_registry.py -q
```

Result: **14 passed**.

Coverage includes canonical identity, schema rejection, event hash chaining,
tamper detection, idempotent append, collision rejection, stale chain links,
Zenith binding, integrity tiers, SQLite rebuild parity, index tamper rejection,
verifier status, and safety blocking.

## Real read-only Zenith artifact

Input: `outputs/market_update_20260720_160414` captured from `LIVE_MT5`.

Registry record result:

```text
source_class: LIVE_MT5
integrity_tier: VERIFIED
events: 9
analyses: 1
views: 1
decisions: 4
evidence_refs: 18
status: PASS
trade_write_enabled: false
auto_execution_enabled: false
order_actions: 0
permission_leakage: 0
outcome_labeling: DEFERRED_PHASE_2
```

Commands:

```text
$env:PYTHONPATH="src"; python tools/record_analysis_registry.py --output-dir "D:\\MyWork\\AlgoTrade\\OS\\Zenith Trading System\\Codex_Trading_Lab_Integrated_v0.3.1-shockfix\\outputs\\market_update_20260720_160414" --ledger outputs/analysis_registry/events.jsonl
$env:PYTHONPATH="src"; python tools/rebuild_analysis_registry.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite
$env:PYTHONPATH="src"; python tools/verify_analysis_registry.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite
```

The source output directory was read only. Recording the same output twice
returned the same event IDs and did not add duplicate ledger rows.

## Repository validation

Targeted registry tests passed. The full target-project suite reported **92
passed, 2 failed**. Both failures are pre-existing Sprint 10/TFI harness issues
outside this feature:

```text
tests/test_sprint10_snapshot_harness.py::test_full_pipeline_identity_harness_and_restart_recovery
tests/test_sprint10_snapshot_harness.py::test_forward_harness_attaches_fresh_tfi_from_provider_without_authority_change
TypeError: LiveRuntime.process_snapshot() got an unexpected keyword argument 'tfi_shadow_source'
```

The same two failures were present before Phase 1 implementation (baseline was
78 passed, 2 failed before registry tests were added). No registry code is on
either failing stack path.

`python tools/run_all_validation.py --output outputs/analysis_registry_phase1_validation`
completed all non-pytest checks and reported only the same `pytest` failure.
The successful checks included Basic Eyes, Advanced Eyes, Decision Core,
Permission Agent, live runtime, replay, learning, and worker validation. The
learning check retained `edge_status=INSUFFICIENT_EVIDENCE` and did not change
production policy. Safety outputs retained auto-execution disabled.

## Known Phase 2 deferrals

- Closed-bar outcome label workers and horizon scheduling.
- `MODEL_OUTCOME` and `MANUAL_TRADE_OUTCOME` resolution.
- External and Comparison ingestion with matched cohorts.
- Historical output/chat migration tiers.
- Accuracy, expectancy, calibration, filter-lift, and drawdown reports.
- Dashboard projections and upgrade governance gates.

## Decision

Phase 1 registry foundation is **READY_FOR_PHASE_2_DESIGN**, subject to the two
pre-existing TFI harness failures remaining separately tracked. It is an audit
trail and evidence index; it does not establish trading edge, create Candidates,
grant Permission, or execute broker actions.
