# Sprint 10 Implementation Plan

Implemented scope:

1. Add standalone read-only snapshot adapter package.
2. Add fixture adapter and real MetaTrader5 adapter with fail-closed behavior.
3. Add snapshot QC for required timeframes, closed bars, gaps, duplicate bars, ordering, OHLC validity, freshness, and mixed-time warning.
4. Add append-only evidence writer with raw/normalized/quarantine/latest layout.
5. Add integration harness that runs snapshot -> QC -> decision core -> watcher/runtime -> queue -> scripted worker -> integrity checks.
6. Add forward-shadow CLI.
7. Add tests covering unavailable MT5, symbol unavailable, fixture identity, QC failures, evidence collision, path traversal, harness, and pending/real shadow path.

Non-scope:

- No broker order placement/modification/cancel/close.
- No auto execution.
- No policy/schema breaking change.
- No live model provider integration.
- No TradingOS adapter.
