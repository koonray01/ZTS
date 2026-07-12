---
document_version: 0.2.0
status: FINAL
project: Codex Trading Lab
owner: quality_owner
last_updated: 2026-07-12
---

# Sprint 0 Test Report

## Decision
`PASS`

## Contract validation
- JSON Schemas: 5/5 valid
- Valid examples: 5/5 accepted
- Invalid examples: 5/5 rejected

## Automated tests
- Total: 17
- Passed: 17
- Failed: 0
- Errors: 0

## Verified controls
- Open candles rejected by snapshot schema.
- Sensor-level trade signals rejected.
- Market packet cannot grant permission.
- Entry candidate cannot grant permission.
- Scenario numeric probability rejected before calibration.
- Manual execution locked in project configuration.
- Core documents contain version/status/owner/date metadata.
- No placeholder schema remains.
- No forbidden cross-system source/config dependency detected.
- No public order-write command exists.

## Not tested
- Real MT5 connection
- Real broker timestamps
- Twenty consecutive live snapshots
- Windows filesystem atomicity
- Restart/reconnect behavior

These belong to Sprint 1 and must not be claimed as passed.
