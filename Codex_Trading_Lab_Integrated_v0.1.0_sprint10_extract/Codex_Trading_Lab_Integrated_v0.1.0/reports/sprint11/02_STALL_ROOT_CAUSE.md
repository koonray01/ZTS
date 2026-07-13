# Sprint 11 Stall Root Cause

Status: `INSTRUMENTATION_READY`

## Prior Incident

Sprint 10 attempted:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --output outputs/sprint10_real_forward_shadow_2h
```

Result: `TIMED_SHADOW_INTERRUPTED_STALL`

- Requested snapshots: 120
- Raw snapshots observed: 41
- Normalized decisions observed: 41
- Final report: not written because process did not complete
- Observed stall: multi-hour gap between snapshot 40 and snapshot 41

## Sprint 11 Instrumentation Added

Each iteration now writes an atomic diagnostics file under:

```text
<output>/diagnostics/iteration_<NNN>.json
```

Fields include:

- iteration identity: `iteration_index`, `run_id`, `snapshot_id`
- timing: `iteration_started_at`, `iteration_completed_at`, `last_heartbeat_at`
- stage state: `current_stage`, `current_stage_started_at`
- stage timings: snapshot capture, QC, evidence write, Basic Eyes, Advanced Eyes, Fusion, Scenario, Entry, Watcher, Worker and knowledge output
- terminal context: `terminal_connected`, `symbol_synchronized`, `last_tick_age_seconds`
- timeout state: `timeout_triggered`, `timeout_category`, `timeout_elapsed_seconds`, `recoverable`

Snapshot capture is wrapped with a fail-closed timeout. If it exceeds `--max-snapshot-seconds`, the harness records a `STAGE_TIMEOUT` with category `DATA_COPY_TIMEOUT`, stops the run and returns a non-accepted result.

## Root Cause Categories Supported

- `MT5_API_BLOCK`
- `TERMINAL_UNRESPONSIVE`
- `SYMBOL_SYNC_DELAY`
- `DATA_COPY_TIMEOUT`
- `FILE_WRITE_STALL`
- `LOCK_CONTENTION`
- `PIPELINE_STAGE_STALL`
- `WORKER_STALL`
- `SYSTEM_SLEEP_OR_SUSPEND`
- `CLOCK_JUMP`
- `UNKNOWN_STALL`

## Validation

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest tests/test_sprint10_snapshot_harness.py -q` | 0 | 9 passed |
| `python tools/run_sprint10_harness.py --output outputs/sprint11_fixture_harness_diagnostics2 --iterations 3` | 0 | Fixture diagnostics files written |
| `python -m pytest -q` | 0 | 42 passed |
| `python tools/run_all_validation.py --output outputs/sprint11_validation_after_diagnostics` | 0 | 9 checks passed |
| `python -m compileall -q src tools tests` | 0 | PASS |
| `rg -n "...trade-write tokens..." src tools` | 1 | No forbidden runtime trade-write token matches |

## Current Finding

`ROOT_CAUSE_PENDING_CANARY`

The previous stall cannot be conclusively classified from Sprint 10 artifacts because per-stage heartbeat files did not yet exist. Sprint 11 canary and timed shadow runs will classify any new stall using the diagnostics above.
