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

This feature extends the existing conditional-decision contract. The current
scheduler treats only `CONDITIONAL_DIRECTIONAL` as activation-gated; the
implementation must add an explicit `CONDITIONAL_SETUP` subtype rather than
pretend that an ordinary `SINGLE_TARGET_SETUP` can wait for a closed-bar
activation.

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
- Minimum frozen reward-to-risk: 0.50.
- Remains research-only and is never promoted from its own results.

### `VERY_RELAXED`

- Requires a closed-bar response at the selected zone.
- Requires the activation timeframe leg not to oppose the branch.
- Does not require full context alignment or follow-through plus retest.
- Minimum frozen reward-to-risk: 0.75.

### `RELAXED`

- Requires a closed-bar break or reclaim.
- Requires activation-timeframe structure to support the branch.
- Requires at least one context timeframe not to contradict the branch.
- Follow-through or retest is required, but not both.
- Minimum frozen reward-to-risk: 1.00.

### `NORMAL`

- Requires break or reclaim, follow-through, and a failed or successful retest
  appropriate to the branch.
- Requires activation and context timeframe alignment.
- Minimum frozen reward-to-risk: 1.50.
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

## Deterministic Geometry

Geometry is derived before future evidence is visible:

1. Select the nearest active validated zone appropriate to the branch:
   demand/support for BUY and supply/resistance for SELL.
2. Prefer activation-timeframe zones; fall back to the nearest context
   timeframe zone only when the activation timeframe has none.
3. Freeze an entry price or entry band inside that zone.
4. Place structural invalidation beyond the far zone boundary plus a declared
   spread/volatility buffer.
5. Select the nearest opposing validated zone that satisfies the strictness
   level's reward-to-risk floor as the single scoring target.
6. If no valid target satisfies the floor, mark the variant `NON_SCORABLE`
   with `TARGET_OR_RR_UNAVAILABLE`; do not invent a distant target.

The exact zone IDs, bounds, buffer method, quote, spread, and resulting risk
and reward are persisted as provenance. Re-running on the same snapshot and
generation must produce the same geometry and identities.

## Identity and Independence

The four strictness variants for one horizon, direction, and snapshot
generation represent alternative policies applied to the same market
opportunity. They therefore share one `semantic_opportunity_id` and use
distinct `variant_id` values:

`EXPLORATORY`, `VERY_RELAXED`, `RELAXED`, and `NORMAL`.

BUY and SELL use different semantic opportunity IDs. Scalping and Daytrade use
different prediction families. Reporting may compare all raw variants, but
headline opportunity counts must deduplicate the four strictness variants so
they are not falsely treated as four independent opportunities.

## Frozen Setup Contract

Every scorable setup contains:

- system and model attribution;
- snapshot, evidence, view, and analysis bindings;
- horizon, strictness, direction, and variant ID;
- semantic opportunity ID and generation ID;
- activation condition expressed in closed-bar terms;
- activation expiry distinct from outcome-evaluation expiry;
- side-aware entry price or bounded entry zone;
- structural stop;
- exactly one scoring target;
- computed risk, reward, and reward-to-risk ratio;
- activation time and immutable expiry;
- invalidation condition;
- source and price-quality tier;
- strictness policy version and geometry-policy version;
- safety assertion with zero broker actions and zero permission leakage.

The workflow rejects non-finite geometry, an entry outside its frozen zone,
BUY geometry without `stop < entry < target`, SELL geometry without
`target < entry < stop`, or non-positive reward-to-risk.

## Registry and Evaluation Flow

1. Capture and validate one fresh snapshot.
2. Build the sixteen setup variants from the same evidence generation.
3. Validate geometry and evidence completeness independently per variant.
4. Freeze valid `CONDITIONAL_SETUP` decisions in the canonical append-only
   Registry.
5. Schedule one `WAITING_ACTIVATION` job for each scorable variant.
6. Evaluate only closed `LIVE_MT5` bars with QC `PASS` against the frozen
   activation contract.
7. On activation, record an immutable activation event and start the
   setup-outcome evaluation window without changing entry, stop, or target.
8. Collect future bid/ask-aware evidence through bounded foreground catch-up.
9. Resolve each setup using the scorer's exact classifications:
   `ENTRY_NOT_TRIGGERED`, `EXPIRED_UNTRIGGERED`, `TP_FIRST`, `SL_FIRST`,
   `AMBIGUOUS_SAME_BAR`, `UNRESOLVED`, or `INVALID_INPUT`.
10. Rebuild coverage and performance reports.

`CONDITIONAL_SETUP` support requires coordinated schema, recorder, scheduler,
activation, catch-up, index, and reporting changes. A setup must never be
registered as scorable until every required activation and geometry field
passes contract validation.

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

Variant diagnostics show each strictness level separately. Headline reporting
uses one declared representative-selection policy and reports the raw variant
count alongside the deduplicated opportunity count. No result may claim
independent sample size from multiple strictness variants of the same
opportunity.

## Agent and Skill Contract Updates

This feature updates existing routing and domain contracts; it does not create
a competing primary workflow.

### `AGENTS.md`

- Keep `ctl-market-analysis-registry` as the sole primary route for live
  Scalping and Daytrade setup requests.
- State that multi-strictness requests create `CHAT_MODEL /
  CONDITIONAL_WATCH_SETUP` variants, never Zenith Candidates.
- Require one fresh snapshot per setup generation, canonical Registry writes,
  cohort separation, and explicit safety counters.
- Prohibit retrospective geometry, strictness-based blocker weakening, and
  treating variants as independent opportunities.

### `skills/ctl-market-analysis-registry/SKILL.md`

- Add the four supported strictness levels and the 16-variant matrix.
- Require setup class, generation ID, semantic opportunity ID, variant ID,
  scorable status, scheduled-job count, catch-up status, and safety status in
  the response.
- Require fresh evidence and one registration pass; supporting skills must not
  capture another snapshot or duplicate Registry writes.

### `skills/ctl-scenario-planner/SKILL.md`

- Define the closed-bar activation grammar for each strictness level.
- Require both SELL-continuation and BUY-reversal branches when requested.
- Require deterministic zone selection, geometry, invalidation, activation
  expiry, evaluation horizon, and one scoring target.
- Mark incomplete variants `NON_SCORABLE` with explicit reason codes.

### `skills/ctl-entry-evaluator/SKILL.md`

- Recognize `CONDITIONAL_SETUP` lifecycle states and list only immutable,
  snapshot-bound setup geometry.
- Preserve the distinction among `ZENITH_CANDIDATE`,
  `CONDITIONAL_WATCH_SETUP`, and `NO_SETUP`.
- Prohibit Candidate promotion, Permission inference, geometry revision after
  activation, or broker writes.

### Skill and Routing Verification

Pressure tests must show that natural-language requests for Scalping,
Daytrade, both horizons, low strictness, or four-tier setups all route once to
`ctl-market-analysis-registry`. Tests must also show that the supporting skills
reuse the primary snapshot and never cause a second Registry registration.

## Failure Handling

- Invalid or stale market evidence: create no setup and report the failed gate.
- Blocking deterministic risk: create no setup and report `NO_SETUP`.
- Partial geometry: freeze only if the Registry supports an explicitly
  `NON_SCORABLE` research record; schedule no evaluation.
- Registry write failure: report `REGISTRY_BLOCKED` and do not claim success.
- Catch-up failure: preserve scheduled work and report `CATCHUP_BLOCKED`.
- Same-bar TP/SL without sufficient refinement: keep the outcome ambiguous.
- Activation expires before a valid closed-bar trigger: resolve
  `EXPIRED_UNTRIGGERED` without starting setup scoring.
- Duplicate request for the same snapshot, generation, and variant: return the
  existing immutable IDs without appending duplicate events or jobs.

## Verification

Tests must prove:

- the full matrix contains sixteen unique variants;
- all variants bind to one fresh snapshot and one generation;
- strictness affects activation evidence but never safety gates;
- Scalping and Daytrade use their declared timeframes and expiries;
- BUY and SELL geometry is side-correct;
- incomplete variants are non-scorable and unscheduled;
- scorable variants schedule evaluation jobs;
- setup jobs begin in `WAITING_ACTIVATION`, activate only on later closed bars,
  and retain their original geometry;
- outcome reporting remains separated by cohort;
- four strictness variants share one semantic opportunity per
  horizon/direction/generation and do not inflate headline sample size;
- repeated creation is idempotent for the same snapshot and generation;
- agent routing and all three skill contracts describe and enforce the same
  matrix, safety rules, and one-snapshot/one-registration boundary;
- `trade_write_enabled=false`, `auto_execution_enabled=false`,
  `order_actions=0`, and `permission_leakage=0` throughout.

## Acceptance Criteria

The feature is complete when a fresh, valid XAUUSD snapshot can produce the
sixteen expected conditional watch variants, freeze every complete variant in
the canonical Registry, schedule their evaluation jobs, report incomplete
variants honestly, and demonstrate through tests and runtime output that no
Candidate promotion, Permission grant, or broker mutation occurred.
