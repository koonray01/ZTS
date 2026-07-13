# Manual Go-Live Runbook

Status: `DRAFT_NOT_APPROVED_FOR_GO_LIVE`

This runbook is for manual-only shadow and operator review. It does not authorize automated broker execution.

## Pre-Market Startup

1. Confirm branch and release commit.
2. Confirm `trade_write_enabled=false`.
3. Confirm `auto_execution_enabled=false`.
4. Confirm `manual_confirmation_required=true`.
5. Start MT5 terminal and log in manually.
6. Confirm target symbol is visible and synchronized.
7. Confirm output path is a fresh directory.

## MT5 Terminal Verification

- Terminal connected: required.
- Account identity: masked in evidence only.
- Broker server: recorded in evidence.
- Last tick age: must remain within freshness policy.
- No order placement API is used by the system.

## Snapshot Health

Run a canary before an operating session:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 10 --interval-seconds 60 --max-snapshot-seconds 300 --output outputs/manual_session_canary
```

Proceed only if the canary is accepted and reports zero order actions.

## Session Operation

Run forward shadow:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --max-snapshot-seconds 300 --output outputs/manual_session_shadow
```

Monitor:

- diagnostics heartbeat files
- raw evidence manifests
- stage timeouts
- candidate count
- Part 3 requests
- worker invocations
- order actions

## Candidate And Part 3

Part 3 `APPROVED` means only that a human may consider opening a trade manually. It never means the system should send, modify, cancel or close an order.

Before a human action, verify:

- candidate is not expired
- snapshot identity matches the current decision
- account context is current
- session is ACTIVE
- no shock lock is active
- manual checklist is complete

## Position Recording And Monitoring

Positions are read-only observations. If a human manually opens a position, record the position externally and use system output only for monitoring context. The system must not modify broker-side stop loss, take profit or position state.

## End Of Session

1. Stop forward shadow.
2. Bundle evidence.
3. Review diagnostics.
4. Record candidate/Part 3 status.
5. Record any unknowns.
6. Keep release artifact separate from evidence bundles.

Evidence bundle command:

```powershell
python tools/bundle_sprint10_evidence.py --evidence-root outputs/manual_session_shadow/evidence --output outputs/manual_session_shadow/evidence_bundle.zip
```
