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
| 2026-07-12T15:15:09Z | `python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --output outputs/sprint10_real_forward_shadow_2h` | 124/tool timeout | Interrupted: 41 raw/normalized snapshots, multi-hour stall between snapshot 40 and 41, process manually stopped |
| 2026-07-12T18:58:37Z | `python -m pytest tests/test_sprint10_snapshot_harness.py -q` | 0 | 9 passed, including forward-shadow acceptance classification |
| 2026-07-12T18:58:37Z | `python tools/run_forward_shadow.py --output outputs/sprint10_real_forward_shadow_timeout_probe3 --snapshots 3 --interval-seconds 0 --max-snapshot-seconds 300` | 2 | Real MT5 smoke only: 3 snapshots, accepted=false, acceptance_status=`REAL_MT5_SMOKE_ONLY`, 0 jobs, 0 worker invocations, 0 order actions |
| 2026-07-12T18:59:31Z | `python -m pytest -q` | 0 | 42 passed after stall/acceptance-status fix |
| 2026-07-12T18:59:31Z | `python tools/run_all_validation.py --output outputs/sprint10_integrated_validation_post_stall_fix` | 0 | 9 integrated checks passed |
| 2026-07-12T18:59:31Z | `python tools/validate_contracts.py` | 0 | 25 schemas passed |
| 2026-07-12T18:59:31Z | `rg -n "...trade-write tokens..." src tools` | 1 | No forbidden runtime trade-write token matches |
| 2026-07-12T14:54:xxZ | `rg ... src tools` | 0 | No runtime trade-write/shell forbidden token matches |
| 2026-07-12T14:54:xxZ | `python tools/bundle_sprint10_evidence.py --evidence-root outputs/sprint10_real_forward_shadow_20/evidence --output outputs/sprint10_real_forward_shadow_20/evidence_bundle.zip` | 0 | Evidence bundle created |

## Matrix Coverage

Covered by tests or CLI: MT5 unavailable, symbol unavailable, valid synchronized snapshot contract, closed-bars-only, stale snapshot, mixed timestamps warning, duplicate bars, missing/gap bars, invalid OHLC, broker/capture metadata, append-only collision, account read-only, position read-only, no order methods, no cross-system runtime dependency, error serialization, full pipeline identity, significant-event job creation, job lease/recovery, worker tool allowlist, permission fabrication rejection, session pause/lock, audit-chain integrity, restart/recovery primitives, replay/live stream separation, no automatic policy promotion, no automatic skill deployment.

Not fully covered: long-duration real market wait, custom indicator repaint audit, real live model provider.
