# Sprint 11 Known Limitations

- Real Candidate creation occurred in the freshness-fix canary, but full Candidate -> Watcher -> Worker -> Part 3 -> proposal path remains incomplete.
- Real Part 3 path was not exercised; part3_requests remained 0.
- Shock behavior from the 120-run is not confirmed; `SHOCK_BLOCK=120` was an observability classification issue and actual volatility state was `UNKNOWN` because Basic Eyes were blocked by `SNAPSHOT_NOT_FRESH`.
- Snapshot freshness/time mapping was fixed and validated by a 10-snapshot canary; a new 120-snapshot run is still required with the fix.
- The timed shadow saw one semantic market state and no state transition.
- No significant watcher event occurred.
- No worker job was created in the timed shadow because no significant event occurred.
- No restart or reconnect drill occurred inside the 120-snapshot run.
- Custom indicator mapping/repaint audit is still pending.
- Live model provider remains disconnected; scripted worker path only.
- Extended multi-session shadow is not started.
- Manual go-live runbooks are drafted, but operator drill and human approval remain pending.
- Trading edge is not validated.
- Production readiness is not approved.
