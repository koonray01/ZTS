# Outcome Policy

Outcome classifications:

- TP_FIRST
- SL_FIRST
- NO_TRIGGER
- EXPIRED
- AMBIGUOUS_SAME_BAR
- MANUAL_OVERRIDE
- OPEN_AT_END

Rules:

- NO_TRIGGER produces `realized_r = 0.0`
- AMBIGUOUS_SAME_BAR is not counted as a clean win
- MANUAL_OVERRIDE sets `entry_engine_credit = false`
- Future knowledge may never repair an earlier decision
