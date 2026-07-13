# Sprint 11 Known Limitations

- Real Candidate path was not exercised; candidate_count remained 0.
- Real Part 3 path was not exercised; part3_requests remained 0.
- The timed shadow saw one semantic market state and no state transition.
- No significant watcher event occurred.
- No worker job was created in the timed shadow because no significant event occurred.
- No restart or reconnect drill occurred inside the 120-snapshot run.
- Custom indicator mapping/repaint audit is still pending.
- Live model provider remains disconnected; scripted worker path only.
- Extended multi-session shadow is not started.
- Manual go-live runbooks still need to be added before any go-live consideration.
- Trading edge is not validated.
- Production readiness is not approved.
