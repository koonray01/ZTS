# Integration Plan

Prerequisites:
- Sprint 1 real snapshot PASS
- Sprint 2–5 shadow verification PASS

Integration:
```text
MT5 Snapshot Service
→ LiveRuntime.process_snapshot(snapshot)
→ Job Queue
→ External Codex Worker (later)
```

No sensor or runtime component may open its own MT5 connection.
