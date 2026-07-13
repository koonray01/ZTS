# Sprint 11 Shock Detector Audit

Status: `SHOCK_BEHAVIOR_CONFIRMED_REAL`

Source analyzed:

```text
outputs/sprint11_real_forward_shadow_2h
```

Analyzer:

```powershell
python tools/analyze_shadow_diagnostics.py --output outputs/sprint11_real_forward_shadow_2h --report-json outputs/sprint11_real_forward_shadow_2h/shock_audit.json
```

## Result

The previously reported `SHOCK_BLOCK=120` should not be interpreted as confirmed real-market shock.

Audit metrics:

- snapshots analyzed: 120
- shock active snapshots: 0
- shock started count: 0
- shock cleared count: 0
- longest shock duration: 0 snapshots
- actual shock trigger reasons: none
- sensor block reasons: `SNAPSHOT_NOT_FRESH=480`

Volatility state by timeframe:

| Timeframe | UNKNOWN | SHOCK |
|---|---:|---:|
| M5 | 120 | 0 |
| M15 | 120 | 0 |
| H1 | 120 | 0 |
| H4 | 120 | 0 |

## Thresholds

Shock detector thresholds in `src/ctl_eyes/volatility.py`:

- true-range ratio shock: `>= 3.0`
- true-range/body shock: `>= 2.0` and body dominance ratio `>= 0.70`
- elevated: `>= 1.8`

No threshold change was made.

## Finding

`SHOCK_BLOCK=120` was an observability classification error:

- The market packet had no blocking shock risk flags.
- Volatility sensors did not compute true-range ratios because the snapshot freshness state blocked Basic Eyes.
- The old suppression breakdown counted tail-risk scenarios as `SHOCK_BLOCK`, which overstated shock behavior.

## Corrective Action

Updated Sprint 11 observability so future runs:

- count `SHOCK_BLOCK` only from actual blocking risk flags
- report sensor freshness/QC blockage as `SNAPSHOT_QC_BLOCK`
- report `primary_suppression_reason`
- report `secondary_suppression_reasons`
- report a candidate funnel

## Freshness Fix Canary

After broker-time normalization and market-session gap handling, a new real MT5 canary was run:

```text
outputs/sprint11_freshness_fix_canary_20260713_102820
```

Result:

- snapshots: 10
- shock active snapshots: 0
- sensor block reasons: none
- M5/M15/H1 volatility: `NORMAL`
- H4 volatility: `HIGH`
- shock input values available for M5/M15/H1/H4: yes
- semantic state hashes: 3
- significant events: 2
- jobs created: 1
- candidates: 90
- order actions: 0

The original 120-run remains classified as `SHOCK_INPUT_MAPPING_ERROR`, but the canary after the fix shows the shock detector can compute inputs and does not remain sticky.

## Decision

`SHOCK_BEHAVIOR_CONFIRMED_REAL`

Reason: session 2 completed 120 real MT5 snapshots after the timestamp/freshness fix.

Session 2:

```text
outputs/sprint11_session_2_20260713_104017
```

Metrics:

- snapshots: 120
- shock active snapshots: 5
- shock started count: 1
- shock cleared count: 1
- longest shock duration: 5 snapshots
- sensor block reasons: none
- shock input values available for all tracked timeframes: yes
- shock timeframe: M5 only
- M5 states: `NORMAL=106`, `HIGH=9`, `SHOCK=5`
- M15 states: `NORMAL=105`, `HIGH=15`
- H1 state: `NORMAL=120`
- H4 states: `HIGH=79`, `NORMAL=41`

This confirms the detector recalculates from current snapshot inputs, does not stay sticky across the session, and can clear.
