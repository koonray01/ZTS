# Session Start Checklist

- Confirm execution mode: `MANUAL_ONLY`.
- Confirm `trade_write_enabled=false`.
- Confirm `auto_execution_enabled=false`.
- Confirm MT5 terminal connected.
- Confirm account identity is expected and masked in evidence.
- Confirm broker server is expected.
- Confirm symbol is synchronized.
- Confirm M5/M15/H1 closed bars are available.
- Confirm evidence output path is new for this run.
- Run timed canary before extended shadow.
- Confirm canary has zero order actions and zero permission leakage.
- Start longer shadow only if canary passes.
