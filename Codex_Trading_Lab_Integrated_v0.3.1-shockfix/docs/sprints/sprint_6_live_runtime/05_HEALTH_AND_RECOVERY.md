# Health and Recovery

Health checks:
- snapshot age
- pipeline exception count
- state persistence
- queue write verification
- audit-chain verification
- dependency version state

Critical failures trigger `LOCKED`.
Restart restores:
- session state
- previous decision state
- seen watcher keys
- queued jobs
- registered plans
- observed positions
