# Next Real Integration

## Required order
1. Implement a standalone MT5 Snapshot Service.
2. Verify broker time, closed-bar integrity and freshness.
3. Map and audit any custom MQL5 indicators for repaint/future leakage.
4. Run the complete pipeline in forward shadow mode.
5. Connect a real model provider only after worker security tests pass locally.
6. Collect enough real episodes before evaluating edge or changing policy.

## Explicitly prohibited during Sprint 10
- broker order sends
- automatic SL/TP modification
- automatic policy promotion
- importing state from TradingOS main
