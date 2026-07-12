---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: quality_owner
last_updated: 2026-07-12
---

# QA / QC / Verify / Validate Policy

## QC — runtime data quality
Checked on every snapshot:
- MT5 connection and terminal identity,
- symbol availability,
- capture and broker timestamps,
- freshness threshold,
- synchronized timeframe cutoffs,
- closed bars only,
- gaps and duplicates,
- invalid OHLC,
- indicator/version identity where present,
- mixed-run and mixed-time rejection.

## QA — engineering quality
Required for every implementation:
- unit tests,
- integration tests,
- JSON Schema tests,
- golden fixtures,
- regression tests,
- red-team/error cases,
- deterministic reproducibility,
- run report and known gaps.

## Verify — implementation against specification
Examples:
- open candles cannot appear in analytical bar arrays,
- a wick through a level is not a close-confirmed break,
- a scenario cannot skip required nodes,
- stale data cannot become live permission,
- Codex cannot override deterministic output,
- an entry candidate cannot authorize execution.

## Validate — market usefulness
Measured after verified implementation:
- opportunity count per session/day,
- candidate count by entry type,
- approval rate,
- entry latency,
- blocked winners versus blocked losers,
- false approvals,
- missed valid setups,
- expectancy by setup/regime/session,
- token cost per useful decision.

## Critical distinction
`VERIFY PASS` does not imply `VALIDATE PASS`. Correctly implemented logic may still have no trading value.

## Release decisions
- `PASS`: all mandatory criteria met.
- `CONDITIONAL_PASS`: no safety violation; explicit accepted gaps remain.
- `FAIL`: contract or tests not met.
- `QUARANTINE`: evidence or provenance cannot be trusted.
