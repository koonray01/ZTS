# Watcher Runtime Policy v0.1

Watcher runs only after a validated snapshot is processed.

## Significant triggers
- market state change
- shock detected/cleared
- zone touched/invalidated
- opportunity state change
- scenario rank/status change
- entry window opened/invalidated/expired
- position state change
- data stale or pipeline error

## Controls
- deduplicate by deterministic event key
- debounce repeated events for a configured interval
- persist seen keys across restart
- never invoke Codex for identical state
