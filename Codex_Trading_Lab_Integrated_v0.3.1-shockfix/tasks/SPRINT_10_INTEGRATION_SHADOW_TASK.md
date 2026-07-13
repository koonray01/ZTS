# Sprint 10 — Integration Harness & Forward Shadow Validation

## Mission
Connect the standalone real MT5 snapshot source to the integrated repository and
run end-to-end forward shadow sessions without broker execution.

## Definition of Done
- real closed-bar snapshots pass schema and freshness QC
- all sensor and decision packets validate
- watcher deduplication works over restart
- worker receives jobs through the queue
- live provider adapter is isolated and audited
- Part 3 remains deterministic and manual-only
- no order-write API exists
- at least one complete forward-shadow session report is produced
- failures, latency and token use are measured
- GO/NO-GO decision is evidence based
