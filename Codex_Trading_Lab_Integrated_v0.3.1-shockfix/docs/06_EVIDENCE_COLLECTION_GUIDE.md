# Evidence Collection Guide

Evidence layout:

```text
data/evidence/raw/<YYYY>/<MM>/<DD>/<run_id>/
data/evidence/normalized/<YYYY>/<MM>/<DD>/<run_id>/
data/evidence/quarantine/<YYYY>/<MM>/<DD>/<run_id>/
```

Sprint 10 CLI output uses the same structure under the selected output directory, for example:

```text
outputs/sprint10_real_forward_shadow_20/evidence/raw/...
```

Bundle evidence:

```powershell
python tools/bundle_sprint10_evidence.py --evidence-root outputs/sprint10_real_forward_shadow_20/evidence --output outputs/sprint10_real_forward_shadow_20/evidence_bundle.zip
```

Timed 2-hour evidence bundle:

```powershell
python tools/bundle_sprint10_evidence.py --evidence-root outputs/sprint10_real_forward_shadow_2h/evidence --output outputs/sprint10_real_forward_shadow_2h/evidence_bundle.zip
```

Rules:

- Raw snapshots are append-only.
- Duplicate `run_id` with different content is quarantined.
- Latest pointers are written atomically.
- Normalized output records the raw SHA-256 reference.
- Path traversal in `run_id` is blocked.

Analysis Performance Registry:

```text
D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry\events.jsonl
D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry\index.sqlite
```

Record an existing Zenith output without modifying its evidence bundle:

```powershell
$env:PYTHONPATH="src"
python tools/record_analysis_registry.py `
  --output-dir outputs/market_update_<timestamp>
```

Rebuild and verify the read model:

```powershell
$env:PYTHONPATH="src"
python tools/rebuild_analysis_registry.py
python tools/verify_analysis_registry.py
python tools/analysis_registry_status.py
```

Registry events are append-only and hash-chained. Corrections and supersessions
append new events; they never overwrite existing events. `LIVE_MT5`, `REPLAY`,
`SYNTHETIC`, and `CHAT_ONLY` remain separate source classes. `VERIFIED`,
`PARTIAL`, `CHAT_ONLY`, and `UNMATCHED` are separate integrity tiers, and only
`VERIFIED` records are eligible for future headline performance metrics.

The Registry is an audit trail and evidence index. Phase 2 adds frozen model
decisions, durable outcome jobs, source-bound follow-up evidence, deterministic
labels, coverage, and descriptive performance reports. It does not establish
trading edge, create a Candidate, grant Permission, tune policy, or execute a
broker action. Every normal command resolves the workspace-level canonical
configuration before writing; explicit external verification is read-only and
labeled `NON_CANONICAL`.
