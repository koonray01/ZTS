---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: control_plane_owner
last_updated: 2026-07-12
---

# Public Tool and CLI Contract

## Design rule
UI clients, Codex, and automation call one control plane. They do not call internal sensors directly.

## Command root

```bash
ctl <command> [options]
```

During Python implementation the equivalent module form may be:

```bash
python -m codex_trading_lab.cli <command> [options]
```

## Standard response envelope

```json
{
  "contract_version": "0.2.0",
  "request_id": "REQ-...",
  "run_id": "RUN-...",
  "status": "OK",
  "generated_at": "2026-07-12T08:00:00Z",
  "data": {},
  "warnings": [],
  "errors": [],
  "evidence_refs": []
}
```

## Status values
- `OK`
- `PARTIAL`
- `BLOCKED`
- `ERROR`
- `QUARANTINED`

## Public commands

### `snapshot`
```bash
ctl snapshot --symbol XAUUSD --timeframes M5,M15,H1 --bars 500
```
Creates one immutable synchronized snapshot. Sprint 1 scope.

### `analyze`
```bash
ctl analyze --snapshot-id SNAP-... --profile standard
```
Runs approved perception and fusion pipeline. Future sprint.

### `scenarios`
```bash
ctl scenarios --market-packet-id MPKT-...
```
Builds qualitative scenario tree. Future sprint.

### `entries`
```bash
ctl entries --scenario-packet-id SCNP-...
```
Builds candidate entries without execution permission. Future sprint.

### `plan`
```bash
ctl plan --snapshot-id SNAP-... --profile standard
```
Creates a current action plan using the complete approved workflow. Future sprint.

### `audit`
```bash
ctl audit --evidence-id EVID-...
```
Returns provenance, hashes, source, and validation status.

### `train`
```bash
ctl train --mode random --episodes 50
```
Replay/training entry point. Future sprint.

## Public tool equivalents
- `get_fresh_snapshot` → `snapshot`
- `analyze_market` → `analyze`
- `get_scenarios` → `scenarios`
- `get_entry_candidates` → `entries`
- `build_current_action_plan` → `plan`
- `inspect_evidence` → `audit`

## Exit codes
- `0`: OK
- `2`: PARTIAL
- `3`: BLOCKED
- `4`: INPUT/SCHEMA ERROR
- `5`: RUNTIME ERROR
- `6`: QUARANTINED

## Idempotency
A request may include `--request-id`. Repeating the same request ID with identical arguments returns the existing result; different arguments with the same ID are rejected.

## Safety
No public command in MVP may place, modify, cancel, or close an MT5 order.
