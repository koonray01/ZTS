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
