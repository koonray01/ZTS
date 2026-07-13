# Emergency Response Runbook

Status: `DRAFT_NOT_APPROVED`

## Pause

Use emergency pause when evidence is delayed, MT5 connectivity is unstable, candidate identity is unclear, or operator review is interrupted.

Expected behavior:

- No new Part 3 request should be created.
- Position monitoring may continue read-only.
- Evidence remains append-only.

## Lock

Use emergency lock for permission ambiguity, suspected evidence corruption, unexpected worker behavior or any safety concern.

Expected behavior:

- New permission flow is blocked.
- Existing approval cannot be reused.
- Manual operator must review before resume.

## Safety Incident

If any trade-write API or auto execution path is detected:

1. Stop affected work.
2. Record exact file and line.
3. Mark `CRITICAL_SAFETY_REGRESSION`.
4. Do not weaken tests or guards.

## Recovery

1. Preserve evidence bundle.
2. Preserve logs and diagnostics.
3. Restart only after static safety scan passes.
4. Re-run timed canary before any longer session.
