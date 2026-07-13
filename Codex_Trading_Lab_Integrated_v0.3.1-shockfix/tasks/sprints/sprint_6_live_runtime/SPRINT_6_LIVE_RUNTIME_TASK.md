# Sprint 6 — Live Runtime Integration

## Mission
Integrate session controller, watcher runtime, job queue and position monitor.

## Definition of Done
- validated real snapshots processed sequentially
- identical state does not duplicate jobs
- significant events create one job
- PAUSED/LOCKED block new Part 3
- position monitor remains active while blocked
- restart restores state
- audit and queue integrity pass
- no trade-write API
- forward shadow session completed
