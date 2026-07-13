# Integration Plan

Prerequisites:
- Sprint 1–6 contracts pass
- historical source classified and QC'd
- case partition and version frozen

Integration:
```text
Historical Snapshot Source
→ ReplaySession
→ Same Decision Core
→ Submission
→ Judge
→ Episode Store
```

Replay data, ledgers and reports must remain separate from live execution records.
