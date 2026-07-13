# Sprint 11 Timed Shadow Report

Status: `TIMED_FORWARD_SHADOW_PASS`

Command:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --max-snapshot-seconds 300 --output outputs/sprint11_real_forward_shadow_2h
```

The command was launched as a background process and monitored by diagnostics/evidence counts until completion.

Result:

- source: `LIVE_MT5`
- requested_snapshots: 120
- completed_snapshots: 120
- completed_requested_snapshots: true
- manual_termination: false
- stage_timeouts: 0
- unexplained_stalls: 0
- closed_bar_violations: 0
- timestamp_ordering_errors: 0
- mixed_time_errors: 0
- hash_mismatches: 0
- order_actions: 0
- trade_write_enabled: false
- auto_execution_enabled: false
- permission_leakage: 0
- audit_errors: 0
- queue_errors: 0
- evidence_errors: 0
- unexplained_quarantine: 0
- duplicate_jobs: 0
- identical_state_worker_invocations: 0
- worker_invocations: 0
- jobs_created: 0
- significant_events: 0

Runtime metrics:

- unique_semantic_state_hashes: 1
- semantic_state_transitions: 0
- jobs_suppressed: 0
- worker_invocations_per_unique_state: 0.0
- candidate_count: 0
- part3_requests: 0
- quarantine_records: 0
- reconnect_attempts: 0
- reconnect_successes: 0
- diagnostics_files: 120
- raw_evidence_manifests: 120
- evidence_bundle: `outputs/sprint11_real_forward_shadow_2h/evidence_bundle.zip`

Acceptance result: `TIMED_FORWARD_SHADOW_PASS`

Limitations:

- No semantic state transition occurred.
- No significant watcher event occurred.
- No job was created.
- No real Candidate was created.
- No real Part 3 request occurred.

This validates the timed real MT5 shadow runtime stability and safety gates for this session only. It does not validate the real Candidate or real Part 3 paths.

## Post-Run Validation

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest tests/test_sprint10_snapshot_harness.py -q` | 0 | 9 passed |
| `python -m pytest -q` | 0 | 42 passed |
| `python tools/run_all_validation.py --output outputs/sprint11_validation_final_fresh` | 2 | Failed due output/state reuse in validation output path |
| `python tools/run_all_validation.py --output outputs/sprint11_validation_final_unique_20260713_095925` | 0 | 9 checks passed |
| `python tools/bundle_sprint10_evidence.py --evidence-root outputs/sprint11_real_forward_shadow_2h/evidence --output outputs/sprint11_real_forward_shadow_2h/evidence_bundle.zip` | 0 | Evidence bundle created |

The failed validation run was classified as output/state reuse, not a code regression. A unique output directory passed all integrated checks.
