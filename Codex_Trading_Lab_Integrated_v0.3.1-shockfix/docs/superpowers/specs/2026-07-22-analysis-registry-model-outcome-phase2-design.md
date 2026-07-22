# Analysis Performance Registry Phase 2: Model Outcome Evaluation Design

**Date:** 2026-07-22
**Status:** Approved design pending written-spec review
**Scope:** Model outcomes for analyses produced in chat and Zenith; manual trade outcomes are deferred

## 1. Objective

Extend the append-only Analysis Performance Registry so every eligible frozen
analysis can be evaluated against independent future closed-bar evidence. Phase 2
must evaluate directional forecasts, ordered scenarios, entry setups, and
WAIT/HOLD/ABSTAIN decisions without requiring a continuously running process.

The phase evaluates what the model declared. It does not infer whether the user
placed a trade, and it does not mix model outcomes with later manual execution
records.

## 2. Delivery boundary

Phase 2 includes:

- canonical frozen decision contracts;
- durable horizon scheduling and restart-safe catch-up;
- independent follow-up evidence collection;
- directional, scenario, setup, and abstention labelers;
- coverage and model-performance reports;
- automatic catch-up during the normal analysis workflow;
- an optional read-only background worker;
- safe backfill of eligible existing Registry decisions.

Phase 2 excludes:

- broker order placement or modification;
- automatic trading permission;
- manual trade outcome entry and scoring;
- policy auto-promotion or threshold auto-tuning;
- inventing predictions or setups after future prices are known;
- scoring external analysis that has no frozen measurable contract.

## 3. Architecture

```text
Chat/Zenith analysis
        |
        v
Frozen Decision Contract
        |
        v
Durable Horizon Scheduler
        |
        v
Independent Closed-Bar Evidence
        |
        v
Typed Outcome Labelers
        |
        +--> Directional Outcome
        +--> Scenario Outcome
        +--> Setup Outcome
        +--> Abstention Outcome
        |
        v
Coverage Report --> Model Performance Report
```

JSONL remains the append-only source of truth. SQLite is a disposable,
deterministically rebuildable projection used to find due work and query reports.
Evidence bundles store source snapshots, follow-up bars, manifests, and hashes.

## 4. Frozen Decision Contract

Every scorable conclusion is frozen before follow-up evidence is visible. The
contract contains:

- `decision_id`, `analysis_id`, `view_id`, and decision type;
- direction, action, and primary/alternative role when applicable;
- decision time, reference price, and symbol;
- one or more explicit evaluation horizons;
- success, failure, invalidation, and expiry rules;
- decision-time ATR, regime, volatility, and timeframe scope;
- candidate or semantic-opportunity identity when applicable;
- source snapshot, manifest, and evidence hashes;
- engine and labeling-policy versions;
- source QC, freshness, integrity tier, and scorable status.

A conclusion missing measurable criteria is `NON_SCORABLE`. Frozen fields are
never overwritten. A correction or supersession is appended as a new event and
preserves the original record.

## 5. Durable scheduling and non-continuous operation

Each `(decision_id, horizon, labeling_policy_version)` produces one stable
evaluation job. Jobs move through:

```text
PENDING -> DUE -> EVIDENCE_COLLECTED -> LABELED
```

Terminal alternatives are:

- `INVALID_INPUT`;
- `INSUFFICIENT_FOLLOWUP`;
- `AMBIGUOUS`;
- `UNRESOLVABLE`;
- `NON_SCORABLE`;
- `SUPERSEDED`.

The scheduler persists jobs in Registry events and the SQLite projection. It
does not rely on process memory. On every normal analysis command, the
orchestrator runs bounded catch-up: verify the Registry, find due jobs, collect
available historical closed bars, label eligible jobs, and append reports.

An optional read-only background worker performs the same operation on a timer.
If it stops or the computer is off, no state is lost. The next analysis command
or explicit catch-up command processes overdue jobs. Duplicate evaluation is
prevented by the stable job identity and append-only idempotency checks.

## 6. Follow-up evidence rules

Only bars whose closed timestamps are strictly after the decision time are
eligible. Evidence collection records:

- evaluation-window open and close;
- highest high and lowest low;
- favorable and adverse excursion;
- decision-time ATR and normalized movement;
- bid/ask and spread when required by the decision type;
- bar identifiers, source class, timestamps, manifests, and hashes;
- missing bars, retrieval gaps, source conflicts, and QC results.

Future leakage causes `UNRESOLVABLE`. A decision-time snapshot marked
`QUARANTINE` or `BLOCKED` produces `INVALID_INPUT` and is excluded from accuracy
and edge metrics. Conflicting histories produce `EVIDENCE_CONFLICT`, represented
as an unresolvable outcome rather than a win or loss.

## 7. Outcome policies

### 7.1 Directional outcomes

Each horizon resolves independently to `CORRECT`, `INCORRECT`, `NEUTRAL`,
`AMBIGUOUS`, `INSUFFICIENT_FOLLOWUP`, or `INVALID_INPUT`. The labeler uses
directional return, favorable/adverse excursion, and decision-time
ATR-normalized thresholds so immaterial movement is not counted as accuracy.

### 7.2 Scenario outcomes

Scenarios are evaluated as ordered paths with activation, required events,
invalidation precedence, expiry, and event order. Results are `CONFIRMED`,
`PARTIALLY_CONFIRMED`, `INVALIDATED`, `EXPIRED_UNTRIGGERED`, `UNRESOLVED`, or
`INVALID_INPUT`. Primary and alternative scenarios are scored separately.

### 7.3 Setup outcomes

Setup evaluation is closed-bar and bid/ask aware. It measures entry touch,
TP/SL precedence, MFE, MAE, realized R, worst-realistic-fill R, time to entry,
time to outcome, and expiry. Results are `TP_FIRST`, `SL_FIRST`,
`ENTRY_NOT_TRIGGERED`, `EXPIRED_UNTRIGGERED`, `AMBIGUOUS_SAME_BAR`, `UNRESOLVED`,
or `INVALID_INPUT`.

### 7.4 WAIT/HOLD/ABSTAIN outcomes

Abstention evaluation requires a decision-time frozen candidate or explicitly
defined control. It may produce `PROTECTED_FROM_LOSS`, `MISSED_WINNER`,
`CORRECT_PATIENCE`, `UNNECESSARY_DELAY`, `NO_MATERIAL_OPPORTUNITY`,
`NOT_SCORABLE`, or `INVALID_INPUT`. The system never synthesizes a retrospective
candidate from revealed prices.

## 8. Registry events and projections

Phase 2 adds typed payload schemas and final outcome events while retaining
existing Phase 1 events. Required event concepts are:

- frozen decision recorded;
- evaluation job scheduled;
- follow-up evidence attached;
- model outcome resolved or explicitly unresolved;
- coverage report emitted;
- performance report emitted;
- correction or supersession appended.

SQLite adds queryable projections for frozen decision attributes, evaluation
jobs, evidence status, typed outcomes, and report cohorts. Direction, horizon,
reference price, QC eligibility, policy version, and outcome are first-class
columns rather than fields available only inside JSON.

## 9. Coverage before performance

Coverage reports disclose totals by source, integrity tier, decision type,
horizon, timeframe, outcome state, missing evidence, invalid input, unresolved
reason, and audit error. Performance conclusions become
`INSUFFICIENT_EVIDENCE` when coverage requirements fail.

Every rate shows numerator, denominator, pending count, unresolved count,
excluded count, cohort identity, and uncertainty appropriate to the sample.
Only eligible `VERIFIED` model outcomes enter headline metrics.

## 10. Performance reports

Reports slice results by system, symbol, trade style, horizon, regime,
volatility, direction, decision type, engine version, and labeling-policy
version. They include:

- directional accuracy and directional coverage;
- scenario confirmation, partial-confirmation, and invalidation rates;
- setup trigger, TP-first, and SL-first rates;
- expectancy R, profit factor, MFE, MAE, and drawdown proxy;
- missed-winner and loss-avoidance rates;
- filter lift and abstention quality;
- calibration error only when a frozen calibrated probability exists.

Every aggregate drills down to Registry events and immutable evidence.
Synthetic/replay cohorts remain separate and cannot establish live trading edge.

## 11. Automatic workflow integration

The normal analysis command performs a bounded catch-up cycle and then records
the new frozen decisions. Catch-up failure does not fabricate outcomes and does
not enable trading. The analysis response reports whether catch-up was complete,
partial, deferred, or blocked.

Explicit operator commands are also provided for:

- catch-up without running a new analysis;
- inspecting pending and overdue jobs;
- rebuilding and verifying SQLite projections;
- producing coverage and performance reports;
- starting, checking, and stopping the optional background worker.

The background worker is read-only with respect to trading. It may append
Registry and evidence artifacts but must always report zero order actions,
`trade_write_enabled=false`, and `auto_execution_enabled=false`.

## 12. Historical backfill

Backfill processes only existing decisions that were frozen before their
follow-up window and have adequate decision-time evidence. It never converts
chat prose into a precise target, stop, horizon, or direction after future data
is visible.

Records are classified as:

- `BACKFILL_ELIGIBLE`;
- `NON_SCORABLE_LEGACY`;
- `INVALID_INPUT`;
- `INSUFFICIENT_EVIDENCE`.

Backfilled cohorts are identified separately from native Phase 2 cohorts.

## 13. Error handling and safety

The system fails closed when hashes, timestamps, source identity, future-leakage
checks, or safety invariants fail. Network or MT5 history failures retain jobs
for retry. Missing bars never become negative outcomes. Same-bar TP/SL ambiguity
is preserved. Re-running catch-up is idempotent.

No outcome, report, scheduler, catch-up command, or background worker may place,
modify, cancel, or recommend automatic execution of an order.

## 14. Test strategy

Tests cover:

- schema and frozen-field validation;
- stable job identity and duplicate suppression;
- restart and overdue-job catch-up;
- strict post-decision closed-bar selection;
- future-leakage and conflicting-history rejection;
- directional thresholds and multi-horizon independence;
- ordered scenario event evaluation;
- bid/ask-aware setup outcomes and same-bar ambiguity;
- abstention controls without retrospective setup invention;
- invalid-input and insufficient-follow-up exclusion;
- deterministic SQLite rebuild parity;
- report numerator/denominator drill-down;
- background-worker restart safety;
- zero order actions and zero permission leakage.

## 15. Delivery sequence

1. Frozen decision contracts and Registry event/schema evolution.
2. Durable scheduler, catch-up engine, and follow-up evidence bundles.
3. Directional and scenario labelers.
4. Setup and WAIT/HOLD/ABSTAIN labelers.
5. Coverage and model-performance reports.
6. Normal-analysis integration and operator CLI commands.
7. Optional read-only background worker.
8. Conservative historical backfill and end-to-end acceptance audit.

Each delivery must be independently testable and preserve the Phase 1 ledger,
hash-chain verification, rebuildability, and trading-safety contract.

## 16. Acceptance criteria

Phase 2 is complete when:

1. Every new scorable model decision has a frozen measurable contract.
2. Every contract creates stable durable jobs for its declared horizons.
3. Overdue jobs resolve after restart without continuous operation.
4. Each eligible decision receives a typed outcome or an explicit unresolved
   reason.
5. Invalid or quarantined input never enters accuracy or edge metrics.
6. Coverage reports reconcile exactly with Registry events.
7. Performance aggregates drill down to decisions, outcomes, and evidence.
8. Rebuilding SQLite from JSONL produces identical projections and counts.
9. Re-running catch-up creates no duplicate outcomes.
10. Normal analysis automatically performs bounded catch-up.
11. The optional worker can stop and resume without state loss.
12. All Phase 1 integrity and safety tests continue to pass.
13. Order actions and permission leakage remain zero.

## 17. Deferred follow-on

Manual trade outcomes will be introduced in a later delivery with user-confirmed
entry, exit, size, spread, slippage, partial closes, and timestamps. They will
reference model decisions but remain a separate account and never replace model
outcomes.
