# Sprint 10 Test Execution Index

| Time UTC | Command | Exit | Result |
|---|---|---:|---|
| 2026-07-12T14:47:14Z | `python -m pytest -q` | 0 | 33 passed baseline |
| 2026-07-12T14:47:14Z | `python tools/run_all_validation.py --output outputs/sprint10_baseline_validation` | 0 | 9 checks passed baseline |
| 2026-07-12T14:56:38Z | `python -m pytest -q` | 0 | 41 passed after Sprint 10 |
| 2026-07-12T14:56:39Z | `python tools/run_sprint10_harness.py --output outputs/sprint10_fixture_harness_final --iterations 3` | 0 | Fixture harness passed |
| 2026-07-12T14:56:39Z | `python tools/run_all_validation.py --output outputs/sprint10_integrated_validation_final` | 0 | 9 integrated checks passed |
| 2026-07-12T14:56:39Z | `python tools/validate_contracts.py` | 0 | 25 schemas passed |
| 2026-07-12T14:53:53Z | `python tools/run_forward_shadow.py --output outputs/sprint10_real_forward_shadow_20 --snapshots 20` | 0 | Real MT5 rapid forward shadow passed |
| 2026-07-12T15:11:24Z | `python tools/run_forward_shadow.py --output outputs/sprint10_real_forward_shadow_20_dedup2 --snapshots 20 --interval-seconds 0` | 0 | Real MT5 rapid rerun after dedup fix: 20 snapshots, 1 semantic state, 0 jobs, 0 worker invocations |
| 2026-07-12T14:54:xxZ | `rg ... src tools` | 0 | No runtime trade-write/shell forbidden token matches |
| 2026-07-12T14:54:xxZ | `python tools/bundle_sprint10_evidence.py --evidence-root outputs/sprint10_real_forward_shadow_20/evidence --output outputs/sprint10_real_forward_shadow_20/evidence_bundle.zip` | 0 | Evidence bundle created |

## Matrix Coverage

Covered by tests or CLI: MT5 unavailable, symbol unavailable, valid synchronized snapshot contract, closed-bars-only, stale snapshot, mixed timestamps warning, duplicate bars, missing/gap bars, invalid OHLC, broker/capture metadata, append-only collision, account read-only, position read-only, no order methods, no cross-system runtime dependency, error serialization, full pipeline identity, significant-event job creation, job lease/recovery, worker tool allowlist, permission fabrication rejection, session pause/lock, audit-chain integrity, restart/recovery primitives, replay/live stream separation, no automatic policy promotion, no automatic skill deployment.

Not fully covered: long-duration real market wait, custom indicator repaint audit, real live model provider.
