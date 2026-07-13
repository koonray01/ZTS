# Changelog

## 0.3.1-shockfix
- Normalized MT5 broker-time bar timestamps to UTC using measured broker offset.
- Classified market session closure gaps as QC warnings instead of missing live bars.
- Added shock diagnostics analyzer and Sprint 11 shock audit report.
- Added primary/secondary suppression and candidate funnel metrics.
- Recorded session 2 real MT5 evidence: 120 snapshots, 1080 candidates, 16 worker invocations, 0 order actions.

## 0.3.0-readiness
- Added Sprint 11 timed canary and 120-snapshot real MT5 shadow evidence reports.
- Added forward-shadow heartbeat and stall diagnostics.
- Added candidate suppression observability and manual go-live runbooks.

## 0.2.0-sprint10
- Added read-only MT5 snapshot adapter, integration harness and forward-shadow CLI.

## 0.1.0
- Integrated baseline repository.
