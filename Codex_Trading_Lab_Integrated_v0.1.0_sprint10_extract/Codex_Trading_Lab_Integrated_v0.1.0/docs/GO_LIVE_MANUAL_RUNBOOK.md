# Manual Go-Live Runbook

Status: `DRAFT_NOT_APPROVED`

This system remains manual execution only. No software path may place, modify, cancel or close broker orders.

## Startup

1. Confirm branch, commit and release artifact.
2. Confirm MT5 terminal is open, connected and on the intended account.
3. Confirm symbol synchronization for the intended symbol.
4. Run a 10-snapshot timed canary.
5. Confirm snapshot health, closed bars and evidence path.
6. Confirm session state is `ACTIVE`.
7. Confirm active locks are clear.
8. Confirm watcher health.
9. Confirm worker health and tool allowlist.
10. Confirm no trade-write capability by static scan.

## Candidate Review

1. Review candidate status and evidence refs.
2. Confirm Part 3 request uses the same snapshot and candidate identity.
3. Confirm decision has not expired.
4. Confirm `APPROVED` means human review only.
5. Confirm manual execution proposal does not call broker APIs.

## Manual Execution Checklist

1. Human independently verifies symbol, side, entry range, stop, targets and risk.
2. Human opens any trade manually in the broker terminal.
3. Record position details manually.
4. Monitor position with read-only account/position snapshots.

## Shutdown

1. Stop forward shadow.
2. Bundle evidence.
3. Review errors, unknowns, candidate decisions and operator actions.
4. Do not promote observations to policy without approval.
