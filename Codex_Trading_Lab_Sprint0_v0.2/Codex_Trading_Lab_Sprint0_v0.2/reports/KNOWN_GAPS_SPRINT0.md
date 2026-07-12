---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: quality_owner
last_updated: 2026-07-12
---

# Known Gaps After Sprint 0

1. No Python runtime package has been implemented.
2. No real MT5 terminal connection has been executed.
3. Broker symbol naming, timezone, and history availability are unresolved.
4. Freshness thresholds are contract fields but production defaults are not calibrated.
5. Custom indicator buffer/object integration is out of Sprint 1 core scope.
6. Scenario, entry, SMC/ICT, watcher, and training modules are not implemented.
7. Trading edge, opportunity frequency, entry latency, and expectancy remain unknown.
8. No UI/dashboard exists.
9. No future read-only adapter to any other system exists.
10. JSON number handling must be implemented carefully with broker digits; schema validation alone does not guarantee numeric comparison correctness.
