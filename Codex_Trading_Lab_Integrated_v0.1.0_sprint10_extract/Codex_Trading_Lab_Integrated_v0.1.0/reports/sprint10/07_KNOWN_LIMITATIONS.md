# Sprint 10 Known Limitations

- Real forward shadow used rapid capture timing; a longer timed session is still needed before any readiness claim beyond this sprint gate.
- No entry candidates appeared in the real run, so Part 3 real request behavior was not exercised by live market conditions.
- The corrected worker-dedup rapid run produced 0 worker invocations because no significant events occurred over one unique semantic market state.
- Timed forward shadow is pending and must prove closed-bar progression, watcher deduplication over time, restart recovery, and candidate lifecycle behavior.
- Custom MQL5 indicators, buffer mapping, object mapping, and repaint audit remain pending.
- Live model provider remains disconnected; scripted provider was used.
- Historical active examples/reports still contain old absolute `/mnt/data` strings.
- No trading edge is validated.
- This system remains manual-only and not production execution ready.
