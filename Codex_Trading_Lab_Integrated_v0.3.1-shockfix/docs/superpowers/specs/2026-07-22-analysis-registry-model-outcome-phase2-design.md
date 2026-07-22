# Analysis Performance Registry Phase 2: Model Outcome Evaluation Design

**Date:** 2026-07-22
**Status:** Revised after second technical review; pending final user approval
**Scope:** Model outcomes for analyses produced in chat and Zenith; manual trade outcomes are deferred

## 1. Objective

Extend the append-only Analysis Performance Registry so every eligible frozen
analysis can be evaluated against outcome-blind, source-bound future closed-bar
evidence. Phase 2
must evaluate directional forecasts, ordered scenarios, entry setups, and
WAIT/HOLD/ABSTAIN decisions without requiring a continuously running process.

The phase evaluates what the model declared. It does not infer whether the user
placed a trade, and it does not mix model outcomes with later manual execution
records.

## 2. Delivery boundary

Phase 2 includes:

- canonical frozen decision contracts;
- durable horizon scheduling and restart-safe catch-up;
- outcome-blind, source-bound follow-up evidence collection;
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
Outcome-Blind Source-Bound Follow-up Evidence
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
Here, outcome-blind means the evidence collector does not inspect the predicted
label while collecting bars; it does not imply an independent market-data
vendor.

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

The canonical decision types are `DIRECTIONAL`, `SCENARIO`, `SETUP`, and
`ABSTENTION`. A directional decision additionally declares
`UNCONDITIONAL_DIRECTIONAL` or `CONDITIONAL_DIRECTIONAL`. Phase 1 `ACTION_PLAN`
records remain readable but are not promoted to a Phase 2 type unless their
decision-time payload already satisfies the full contract. The labeling policy
version is frozen with the decision.

Conditional decisions freeze a machine-readable activation condition and use:

```text
RECORDED -> WAITING_ACTIVATION
         -> ACTIVATED -> FOLLOWUP_PENDING -> RESOLVED
         -> EXPIRED_UNTRIGGERED
         -> INVALIDATED_BEFORE_ACTIVATION
```

Their evaluation clock starts at the first qualifying closed-bar activation,
not at decision time. An unconditional decision starts at decision time.

Reference-price semantics are also frozen:

- directional forecasts use decision-time `mid`;
- BUY entry touch uses `ask`, while BUY TP/SL uses `bid`;
- SELL entry touch uses `bid`, while SELL TP/SL uses `ask`;
- `MID_ONLY_PROXY` is permitted only when bid/ask history is unavailable and
  remains a separate, non-bid/ask-aware cohort;
- decision-time and follow-up spread provenance remain explicit.

MT5 rate bars are treated as bid OHLC. When a bar contains validated
`spread_points` and the frozen symbol `point`, ask OHLC is reconstructed as
`bid + spread_points * point`, and mid as the average of bid and reconstructed
ask. A missing or invalid bar spread forces `MID_ONLY_PROXY` for directional
evaluation and prevents that bar from resolving a bid/ask-aware setup outcome.

Setup evidence declares one execution-price quality tier:

- `TRUE_BID_ASK_TICKS` when source-bound tick history proves event order;
- `BAR_SPREAD_RECONSTRUCTED` when ask prices are approximated from bid OHLC and
  bar spread;
- `MID_ONLY_PROXY` when neither bid/ask ticks nor valid bar spread exists.

These tiers remain separate cohorts. `BAR_SPREAD_RECONSTRUCTED` is useful for
model diagnostics but is not described as actual-fill or execution-realistic
evidence. `MID_ONLY_PROXY` cannot resolve a setup outcome.

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

### 5.1 Horizon resolution

Every duration horizon uses one deterministic clock policy:

```text
evaluation_start = decision_time for unconditional decisions
evaluation_start = activation_bar.close_time for conditional decisions
evaluation_deadline = evaluation_start + horizon
terminal_bar = first eligible bar whose close_time >= evaluation_deadline
terminal_price = terminal_bar.close
excursion_window = eligible closed bars from evaluation_start through terminal_bar
```

The excursion window begins at `evaluation_start` for every decision type.

An eligible bar must have `open_time >= evaluation_start`; a bar that contains
the decision or activation instant is excluded even if it closes afterward.
When source bars omit `open_time`, the collector may derive it only from a
declared fixed timeframe and must record the derivation. Horizons expressed as
market sessions must declare an explicit calendar and timezone; Phase 2
initially supports duration horizons only.

### 5.2 Single-writer safety

Analysis commands, explicit catch-up commands, and the background worker share
one Registry writer lease. The lease has an owner ID, acquisition time,
heartbeat, and deterministic expiry/recovery policy. Only the lease holder may
append events or replace the SQLite projection. JSONL is never rewritten: the
writer appends exactly one complete line, flushes and fsyncs it, then verifies
the stored event hash while still holding the lease. SQLite is rebuilt into a
temporary database, parity-checked against JSONL, and atomically replaced.
Evidence files use temporary creation, hashing, and atomic rename. A partial
JSONL tail blocks normal mutation and requires an explicit audited recovery;
the verifier never truncates it silently. A lease conflict defers catch-up; it
never creates a second writer or blocks collection of a new read-only market
snapshot.

## 6. Follow-up evidence rules

Only bars whose open timestamps are at or after `evaluation_start` are eligible.
Evidence collection records:

- evaluation-window open and close;
- highest high and lowest low;
- favorable and adverse excursion;
- decision-time ATR and normalized movement;
- bid/ask and spread when required by the decision type;
- bar identifiers, source class, timestamps, manifests, and hashes;
- missing bars, retrieval gaps, source conflicts, and QC results.

Source-bound consistency requires the same server, account source class,
symbol, symbol specification, broker timezone, and price-digit/point contract.
Overlapping bars are fingerprinted so later broker-history revisions are
visible. Raw manifest hashes bind every collection. Evidence from another
vendor is admitted only to a separately identified cross-source verification
cohort and never silently replaces the broker-bound outcome.

Outcome eligibility is derived from four separate statuses:

- `decision_input_qc` validates the frozen source snapshot;
- `followup_evidence_qc` validates future-bar completeness and freshness;
- `cross_snapshot_consistency_qc` detects conflicting broker histories or
  identity drift;
- `outcome_eligibility` records whether the job may enter metrics.

Future leakage causes `UNRESOLVABLE`. A decision-time snapshot marked
`QUARANTINE` or `BLOCKED` produces `INVALID_INPUT` and is excluded from accuracy
and edge metrics. Conflicting histories produce `EVIDENCE_CONFLICT`, represented
as an unresolvable outcome rather than a win or loss.

For setup precedence, the collector may refine an ambiguous source-timeframe
bar with successively lower closed-bar evidence down to M1, but only from the
same `LIVE_MT5` symbol/source binding with QC `PASS`. If M1 still touches both
boundaries in one bar, or lower-timeframe evidence is missing, the result stays
`AMBIGUOUS_SAME_BAR`. The labeler never assumes optimistic or conservative
precedence.

## 7. Outcome policies

### 7.1 Directional outcomes

Each horizon resolves independently to `CORRECT`, `INCORRECT`, `NEUTRAL`,
`AMBIGUOUS`, `INSUFFICIENT_FOLLOWUP`, or `INVALID_INPUT`. The labeler uses
directional return, favorable/adverse excursion, and decision-time
ATR-normalized thresholds so immaterial movement is not counted as accuracy.

The initial immutable policy is `DIRECTIONAL_TERMINAL_ATR_V1`:

```text
signed_return_atr = direction_sign * (terminal_price - reference_price) / decision_time_atr
CORRECT   when signed_return_atr >= 0.25
INCORRECT when signed_return_atr <= -0.25
NEUTRAL   when -0.25 < signed_return_atr < 0.25
```

`AMBIGUOUS` is reserved for evidence conflict or insufficient temporal
resolution, not small movement. MFE and MAE are reported as diagnostics and do
not change the V1 terminal label. Missing or non-positive decision-time ATR
makes the decision `NON_SCORABLE` under this policy.

### 7.2 Scenario outcomes

Scenarios are evaluated as ordered paths with activation, required events,
invalidation precedence, expiry, and event order. Results are `CONFIRMED`,
`PARTIALLY_CONFIRMED`, `INVALIDATED`, `EXPIRED_UNTRIGGERED`, `UNRESOLVED`, or
`INVALID_INPUT`. Primary and alternative scenarios are scored separately.

Every scenario freezes a canonical ordered event grammar. Each step declares:

- `step_id` and sequence number;
- event type, initially `CLOSED_ABOVE`, `CLOSED_BELOW`, `TOUCHED_BAND`,
  `ENTERED_BAND`, `EXITED_BAND`, or `INVALIDATION_HIT`;
- timeframe, level or band, and side-aware price field;
- whether the step is required or optional;
- activation dependency and `BEFORE`/`AFTER` precedence constraints;
- step deadline and scenario expiry;
- same-bar ambiguity rule and evidence requirements.

Required steps must occur in order. Invalidation wins only when its precedence
is provable; otherwise the scenario remains `UNRESOLVED`. Partial confirmation
equals completed required steps divided by total required steps, but is reported
only when at least one required step completed before expiry. Scenario text is
descriptive and is never parsed by the labeler.

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

An abstention is scorable only when the decision-time record contains either a
fully frozen candidate or a deterministic control with entry, stop, targets,
and expiry. A general WATCH/HOLD without such geometry is `NOT_SCORABLE`.

### 7.5 Policy-version governance

The policy frozen with a decision produces the `ORIGINAL_POLICY_COHORT` and is
the only outcome eligible for live headline metrics. Applying a later policy to
an older decision creates a `RESEARCH_RELABEL_COHORT`; it never overwrites,
supersedes, or changes the original outcome and cannot enter live headline
metrics. Policy promotion remains outside Phase 2.

## 8. Registry events and projections

Phase 2 adds typed payload schemas and final outcome events while retaining
existing Phase 1 events. Required event concepts are:

- frozen decision recorded;
- evaluation job scheduled;
- follow-up evidence attached;
- model outcome resolved or explicitly unresolved;
- immutable audit report published when explicitly requested;
- correction or supersession appended.

Routine coverage and performance reports are deterministic rebuildable
artifacts, not ledger events. An explicit immutable publication appends one
`REPORT_PUBLISHED` event containing the report hash, cohort ID, policy versions,
generation time, and evidence references; it does not embed the full report in
the ledger.

Phase 2 introduces new typed payload schemas without rewriting Phase 1 events.
The verifier dispatches validation by `(event schema version, event_type,
payload schema version)` and continues to accept valid
`ANALYSIS_REGISTRY_EVENT_V0_1` records. New event-envelope versions must retain
hash semantics explicitly; mixed-version ledgers remain one continuous chain.

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

Descriptive counts are publishable from the first resolved record. Rates must
always include Wilson 95% confidence intervals when their outcome is binary.
Directional and scenario rates may be displayed with any non-zero resolved
sample but remain `INSUFFICIENT_EVIDENCE` for validation claims. Setup
expectancy and profit factor are not headline-publishable until at least 30
eligible resolved, triggered setups exist in one declared cohort. No Phase 2
report may claim validated edge, tune policy, or open a promotion gate.

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

The normal analysis command first captures and analyzes a fresh snapshot, then
creates a structured prediction envelope and freezes the current decisions
before running bounded catch-up. This keeps current-market capture independent
from slow historical work. Chat prose is scorable only when the same response
path successfully stores that structured envelope; otherwise the response is
marked `ANALYSIS_NOT_REGISTERED` and cannot be backfilled from prose.

Catch-up failure does not fabricate outcomes and does not enable trading. A
Registry integrity failure blocks Registry mutation but does not prevent a
separate fresh read-only market analysis, which must report
`ANALYSIS_NOT_REGISTERED`. Lease contention, history unavailability, or a
configured work limit defers remaining catch-up. The analysis response reports
whether catch-up was complete, partial, deferred, or blocked, together with
processed and remaining job counts.

Explicit operator commands are also provided for:

- catch-up without running a new analysis;
- inspecting pending and overdue jobs;
- rebuilding and verifying SQLite projections;
- producing coverage and performance reports;
- starting, checking, and stopping the optional background worker.

The background worker is read-only with respect to trading. It may append
Registry and evidence artifacts but must always report zero order actions,
`trade_write_enabled=false`, and `auto_execution_enabled=false`.

Completion is split into two gates. `PHASE2_CORE_COMPLETE` requires the durable
catch-up path and all model-outcome/reporting capabilities but does not require a
resident worker. `PHASE2_WORKER_COMPLETE` additionally requires worker
start/stop, lease-contention, crash-recovery, and restart tests. Worker delivery
is an optional milestone and never blocks the Core gate.

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
- unconditional and closed-bar-activated conditional decisions;
- bid/ask/mid reference-price semantics and proxy-cohort separation;
- stable job identity and duplicate suppression;
- restart and overdue-job catch-up;
- strict post-evaluation-start closed-bar selection;
- future-leakage and conflicting-history rejection;
- directional thresholds and multi-horizon independence;
- ordered scenario event evaluation;
- bid/ask-aware setup outcomes and same-bar ambiguity;
- abstention controls without retrospective setup invention;
- invalid-input and insufficient-follow-up exclusion;
- deterministic SQLite rebuild parity;
- report numerator/denominator drill-down;
- structured chat-envelope registration and `ANALYSIS_NOT_REGISTERED` handling;
- append/fsync failure and partial-tail fail-closed behavior;
- background-worker restart safety;
- zero order actions and zero permission leakage.

## 15. Delivery sequence

1. Frozen decision contracts, structured chat envelopes, and Registry
   event/schema evolution.
2. Durable scheduler, stable job identity, and Registry writer lease.
3. Follow-up evidence collector and cross-snapshot QC.
4. Directional outcome labeler.
5. Ordered scenario outcome labeler.
6. Setup outcome labeler with M1 ambiguity refinement.
7. WAIT/HOLD/ABSTAIN outcome labeler with frozen controls.
8. Coverage and model-performance reports.
9. Normal-analysis integration and operator CLI commands.
10. Optional read-only background worker.
11. Conservative historical backfill and end-to-end acceptance audit.

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
11. `PHASE2_CORE_COMPLETE` does not depend on the optional worker; when the
    worker milestone is delivered, it must stop and resume without state loss.
12. All Phase 1 integrity and safety tests continue to pass.
13. Order actions and permission leakage remain zero.
14. Duration horizons resolve with the documented terminal-bar policy.
15. Same-bar setup ambiguity is never resolved by assumption.
16. Concurrent catch-up attempts cannot create duplicate events or break the
    hash chain.
17. Original-policy and research-relabel cohorts remain separate.
18. Phase 1 event envelopes remain verifiable without ledger rewriting.
19. Decision, follow-up, cross-snapshot, and eligibility QC are independently
    visible.
20. Reports enforce the minimum setup sample and prohibit validated-edge or
    promotion claims during Phase 2.
21. Conditional decisions start their horizon clock only after closed-bar
    activation and can expire untriggered.
22. Directional and setup outcomes enforce the frozen bid/ask/mid semantics.
23. Scenario outcomes consume only the canonical event grammar and never parse
    descriptive prose.
24. JSONL is appended and fsynced under the writer lease and is never rewritten
    during normal operation.
25. Unregistered chat prose cannot be reconstructed into a scored prediction.

## 17. Deferred follow-on

Manual trade outcomes will be introduced in a later delivery with user-confirmed
entry, exit, size, spread, slippage, partial closes, and timestamps. They will
reference model decisions but remain a separate account and never replace model
outcomes.
