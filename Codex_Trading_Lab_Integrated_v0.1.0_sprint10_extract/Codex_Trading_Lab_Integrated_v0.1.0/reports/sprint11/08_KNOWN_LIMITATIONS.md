# Sprint 11 Known Limitations

- Real Candidate creation occurred in the freshness-fix canary and session 2, but full Candidate -> Watcher -> Worker -> Part 3 -> proposal path remains incomplete.
- Session 3 exercised the real Part 3 path 21 times, but each APPROVED result remains manual-only and cannot execute a trade.
- Shock behavior from the 120-run is not confirmed; `SHOCK_BLOCK=120` was an observability classification issue and actual volatility state was `UNKNOWN` because Basic Eyes were blocked by `SNAPSHOT_NOT_FRESH`.
- Snapshot freshness/time mapping was fixed and session 2 completed 120 real snapshots with the fix.
- Session 2 observed 25 semantic market states, 26 watcher events and 16 worker invocations.
- Runtime reload was validated in Session 3. True operating-system process stop/resume and real MT5 reconnect remain pending.
- Session 3's first semantic lifecycle key omitted the stable scenario prefix and produced collision telemetry. The key was corrected after the run; duplicate-semantic acceptance needs a follow-up real run or evidence re-analysis with the corrected key.
- Custom indicator mapping/repaint audit is still pending.
- Live model provider remains disconnected; scripted worker path only.
- Extended multi-session shadow is not started.
- Manual go-live runbooks are drafted, but operator drill and human approval remain pending.
- Trading edge is not validated.
- Production readiness is not approved.
