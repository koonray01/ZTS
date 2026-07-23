# Four-Tier Conditional Watch Setups Design

## Purpose

Create a measurable family of conditional XAUUSD watch setups spanning very
low strictness through the existing normal standard. The family covers both
Scalping and Daytrade horizons and both continuation and reversal directions.
It exists to collect forward evidence and compare trigger quality; it does not
create a Zenith Candidate, grant Permission, or write to the broker.

## Scope

One fresh `LIVE_MT5` snapshot produces sixteen immutable setup variants:

| Dimension | Values |
|---|---|
| Horizon | `SCALPING`, `DAYTRADE` |
| Strictness | `EXPLORATORY`, `VERY_RELAXED`, `RELAXED`, `NORMAL` |
| Directional branch | `SELL_CONTINUATION`, `BUY_REVERSAL` |

Every variant is classified as `CHAT_MODEL` and
`CONDITIONAL_WATCH_SETUP`. Variants are frozen before future price evidence is
known and remain statistically separate by horizon, strictness, and direction.

## Evidence and Safety Preconditions

Creation uses the canonical `ctl-market-analysis-registry` route and exactly one
fresh snapshot. The workflow requires:

- connected MT5 with `source=LIVE_MT5`;
- freshness and source QC `PASS`;
- `trade_write_enabled=false`;
- `auto_execution_enabled=false`;
- no deterministic `BLOCK` that prohibits setup creation;
- an explicit evidence binding to the snapshot, bars, zones, and scenario used.

If a blocking shock or evidence failure exists, the workflow returns
`NO_SETUP` and records the reason. It must not weaken a blocker merely because
the requested strictness is low.

## Setup Matrix

The workflow creates two directional branches at every horizon and strictness.
Each branch has its own immutable decision ID and semantic opportunity ID.

### Scalping

- Context timeframes: M15 and H1.
- Activation timeframe: M5 closed bars.
- Geometry is derived from the nearest validated M5/M15 zone and the fresh
  bid/ask quote.
- Expiry: six M5 closed bars after activation eligibility is frozen.

### Daytrade

- Context timeframes: H1 and H4.
- Activation timeframe: M15 closed bars.
- Geometry is derived from the nearest validated M15/H1/H4 zone and the fresh
  bid/ask quote.
- Expiry: eight M15 closed bars after activation eligibility is frozen.

Expiry is fixed at creation time. A later analysis may create a new generation,
but must not extend or rewrite an existing setup.

## Strictness Levels

Strictness changes activation evidence, not safety, accounting, or broker
boundaries.

### `EXPLORATORY`

- Purpose: maximize forward observations.
- Requires price interaction with the selected zone and one observable
  closed-bar response in the branch direction.
- Does not require cross-timeframe alignment or a completed retest.
- Remains research-only and is never promoted from its own results.

### `VERY_RELAXED`

- Requires a closed-bar response at the selected zone.
- Requires the activation timeframe leg not to oppose the branch.
- Does not require full context alignment or follow-through plus retest.

### `RELAXED`

- Requires a closed-bar break or reclaim.
- Requires activation-timeframe structure to support the branch.
- Requires at least one context timeframe not to contradict the branch.
- Follow-through or retest is required, but not both.

### `NORMAL`

- Requires break or reclaim, follow-through, and a failed or successful retest
  appropriate to the branch.
- Requires activation and context timeframe alignment.
- Uses the existing normal deterministic eligibility standard without
  weakening any gate.

Missing measurable evidence leaves the affected variant `NON_SCORABLE`; no
evaluation job is scheduled for that variant.

## Directional Branches

### `SELL_CONTINUATION`

The setup watches for bearish continuation after a breakdown or rejection.
Activation must be observable on the horizon's activation timeframe. The stop
is above the frozen structural invalidation boundary. The scoring target is the
next validated demand or support objective below entry.

### `BUY_REVERSAL`

The setup watches for demand defense followed by a bullish reclaim. Activation
must be observable on the horizon's activation timeframe. The stop is below
the frozen structural invalidation boundary. The scoring target is the next
validated supply or resistance objective above entry.

The two branches are independent. Triggering one does not silently cancel or
rewrite the other; explicit invalidation or expiry resolves each branch.

## Frozen Setup Contract

Every scorable setup contains:

- system and model attribution;
- snapshot, evidence, view, and analysis bindings;
- horizon, strictness, direction, and variant ID;
- semantic opportunity ID and generation ID;
- activation condition expressed in closed-bar terms;
- side-aware entry price or bounded entry zone;
- structural stop;
- exactly one scoring target;
- computed risk, reward, and reward-to-risk ratio;
- activation time and immutable expiry;
- invalidation condition;
- source and price-quality tier;
- safety assertion with zero broker actions and zero permission leakage.

The workflow rejects non-finite geometry, an entry outside its frozen zone,
BUY geometry without `stop < entry < target`, SELL geometry without
`target < entry < stop`, or non-positive reward-to-risk.

## Registry and Evaluation Flow

1. Capture and validate one fresh snapshot.
2. Build the sixteen setup variants from the same evidence generation.
3. Validate geometry and evidence completeness independently per variant.
4. Freeze valid decisions in the canonical append-only Registry.
5. Schedule one evaluation job for each scorable variant.
6. Collect future bid/ask-aware evidence through bounded foreground catch-up.
7. Resolve each setup as one of:
   `ENTRY_NOT_TRIGGERED`, `TP_FIRST`, `SL_FIRST`,
   `SAME_BAR_AMBIGUOUS`, `GAP_THROUGH_UNRESOLVED`, or `EXPIRED`.
8. Rebuild coverage and performance reports.

The Registry path remains
`D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`.
No checkout, worktree, output folder, or chat session may become an alternate
history root.

## Cohorts and Reporting

Performance is reported separately for:

- Scalping versus Daytrade;
- all four strictness levels;
- SELL continuation versus BUY reversal;
- setup generation and market regime.

Headline metrics deduplicate semantic opportunities according to the existing
Registry policy. Reports expose setup count, trigger rate, TP-first rate,
SL-first rate, ambiguity rate, realized R, and expectancy R. Results remain
`INSUFFICIENT_EVIDENCE` until the existing minimum sample gates are satisfied.
Exploratory results must never be pooled into Normal results.

## Failure Handling

- Invalid or stale market evidence: create no setup and report the failed gate.
- Blocking deterministic risk: create no setup and report `NO_SETUP`.
- Partial geometry: freeze only if the Registry supports an explicitly
  `NON_SCORABLE` research record; schedule no evaluation.
- Registry write failure: report `REGISTRY_BLOCKED` and do not claim success.
- Catch-up failure: preserve scheduled work and report `CATCHUP_BLOCKED`.
- Same-bar TP/SL without sufficient refinement: keep the outcome ambiguous.

## Verification

Tests must prove:

- the full matrix contains sixteen unique variants;
- all variants bind to one fresh snapshot and one generation;
- strictness affects activation evidence but never safety gates;
- Scalping and Daytrade use their declared timeframes and expiries;
- BUY and SELL geometry is side-correct;
- incomplete variants are non-scorable and unscheduled;
- scorable variants schedule evaluation jobs;
- outcome reporting remains separated by cohort;
- repeated creation is idempotent for the same snapshot and generation;
- `trade_write_enabled=false`, `auto_execution_enabled=false`,
  `order_actions=0`, and `permission_leakage=0` throughout.

## Acceptance Criteria

The feature is complete when a fresh, valid XAUUSD snapshot can produce the
sixteen expected conditional watch variants, freeze every complete variant in
the canonical Registry, schedule their evaluation jobs, report incomplete
variants honestly, and demonstrate through tests and runtime output that no
Candidate promotion, Permission grant, or broker mutation occurred.
