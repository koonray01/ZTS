# Four-Tier Conditional Setup Acceptance — 2026-07-23

## Automated verification

- Focused feature suite: 46 passed.
- Full repository suite after compatibility regression coverage: 255 passed.
- Integrated validation: 9 checks passed; zero failures (`outputs/integrated_validation_four_tier_20260723_225745`).

## Live read-only acceptance

- Output: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\market_analysis\setup_matrix_20260723_225511`
- Snapshot: `SNAP_MARKET_ANALYSIS_20260723T155513Z_XAUUSD_20260723T155513Z`
- Evidence: `LIVE_MT5`, `FRESH`, QC `PASS`
- Setup class: `CONDITIONAL_WATCH_SETUP`
- Generation: `SETUP_GENERATION_DCCC997F8BF8F4814C52E55A`
- Variants: 16 total, 16 scorable, 0 non-scorable
- Registry: canonical root, `RECORDED`, 16 evaluation jobs scheduled
- Catch-up: `PARTIAL`, 0 processed, 33 remaining. Conditional jobs are intentionally waiting for activation; this is not a performance result.
- Safety: `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, `permission_leakage=0`

## Compatibility finding

The first acceptance attempt exposed a schema-compatibility issue with historical non-scorable Zenith setup geometry. The Registry failed closed before completing registration. The schema was narrowed so strict numeric geometry applies only to `CONDITIONAL_SETUP`, while legacy `SINGLE_TARGET_SETUP` records remain readable. The canonical SQLite projection was rebuilt from the unchanged append-only ledger and subsequently verified with no integrity errors.

Final Registry verification: `PASS`, 133 events, 100 frozen decisions, 33 evaluation jobs, and no reported integrity errors.

No trading permission or validated edge is claimed.
