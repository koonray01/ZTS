# Analysis Performance Registry Design

**Status:** Approved design pending written-spec review

**Date:** 2026-07-20

**Scope:** Read-only analysis audit, outcome evaluation, comparison, and upgrade governance

**Safety boundary:** Manual Only; no broker writes; no Permission authority

## 1. Purpose

Zenith already preserves snapshots, manifests, decision states, candidate deltas,
claim ledgers, replay evidence, and selected outcome reports. It does not yet have
one durable registry that connects every analysis to its decisions, later market
outcomes, manual trades, scores, comparisons, and upgrade decisions.

The Analysis Performance Registry will provide that connection without modifying
existing evidence. It must support three independently attributable views:

- `ZENITH`: deterministic Zenith runtime analysis.
- `EXTERNAL`: analysis produced outside Zenith, including chat analysis.
- `COMPARISON`: a derived comparison that references frozen Zenith and External
  views without merging or rewriting them.

The registry evaluates all explicit decisions: setups, directional forecasts,
scenarios, `WAIT`, `HOLD`, rejection/filter decisions, and abstentions. It keeps
model performance separate from actual manual-trade execution performance.

## 2. Non-goals and invariants

The registry does not:

- place, modify, cancel, or close broker orders;
- create Candidates or grant Permission;
- rewrite raw evidence, prior session bundles, or ledger events;
- promote a policy, threshold, model, or strategy automatically;
- treat reaction rate, replay success, or safety validation as trading edge;
- mix live, replay, synthetic, or incomplete migrated records in headline
  performance statistics.

`trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`,
and `permission_leakage=0` remain mandatory safety assertions where applicable.

## 3. Chosen architecture

Use a hybrid append-only architecture:

```text
Chat / Zenith Runtime / External Analysis / Manual Trade
                         |
                  Analysis Recorder
                         |
          Append-only Event Ledger (JSONL)
                         |
         Validation and Outcome Label Workers
                         |
             Rebuildable SQLite Read Model
                         |
       Audit Reports / Comparison / Upgrade Gates
```

JSONL is the canonical registry evidence. SQLite is a disposable query index
that must be reproducible from the ledger. Existing Zenith artifacts remain the
canonical evidence for their own content and are referenced by path, identity,
manifest, and hash rather than copied and mutated.

## 4. Components

### 4.1 Analysis Recorder

The recorder accepts frozen analysis artifacts and emits validated events. It
assigns or verifies these stable identities:

- `analysis_id`: one analysis occasion bound to a decision time and market state;
- `view_id`: one `ZENITH` or `EXTERNAL` interpretation of that occasion;
- `comparison_id`: a comparison between compatible frozen views;
- `decision_id`: one independently evaluable claim or action;
- `candidate_id` and `semantic_candidate_id`, when provided by Zenith;
- `evidence_bundle_id`: the evidence bundle supporting the analysis.

Recorder ingestion must be idempotent. Re-ingesting the same source must return
the existing identity or emit an explicit duplicate audit result, never a second
economic observation.

### 4.2 Append-only Event Ledger

Each event contains:

- schema and event versions;
- event ID and event type;
- event time and original decision time;
- source class: `LIVE_MT5`, `REPLAY`, `SYNTHETIC`, or `CHAT_ONLY`;
- integrity tier: `VERIFIED`, `PARTIAL`, `CHAT_ONLY`, or `UNMATCHED`;
- producer, engine/model, policy, configuration, and prompt fingerprints when
  applicable;
- evidence references and source hashes;
- previous-event hash and current-event hash;
- payload and deterministic reason codes.

Required event families include:

```text
ANALYSIS_RECORDED
VIEW_RECORDED
DECISION_RECORDED
CANDIDATE_STATUS_CHANGED
OUTCOME_LABEL_PENDING
MODEL_OUTCOME_RESOLVED
MANUAL_TRADE_RECORDED
MANUAL_TRADE_OUTCOME_RESOLVED
SCORE_CALCULATED
COMPARISON_CALCULATED
CORRECTION_APPENDED
SUPERSESSION_APPENDED
```

Existing events are never edited. Corrections and supersessions reference the
affected event and preserve both histories.

### 4.3 Outcome Label Workers

Workers evaluate frozen decisions only after independent closed-bar follow-up is
available. Evaluation uses both standard horizons (`15m`, `1h`, `4h`, `1d`) and
trade-style horizons (`SCALPING`, `DAYTRADE`, `SWING`). The policy version defines
the exact bars, expiry, price side, ambiguity behavior, and ATR normalization.

Outcome state is one of:

```text
PENDING
PARTIAL_FOLLOWUP
RESOLVED
UNRESOLVABLE
```

Workers must not infer missing decision-time geometry from future price action.

### 4.4 SQLite Read Model

SQLite indexes ledger events into queryable analysis, view, decision, outcome,
trade, score, comparison, and audit projections. It is not a source of truth.
Dropping and rebuilding it from JSONL must reproduce identical logical rows and
aggregates for the same software and policy versions.

## 5. Data model

### 5.1 Analysis

An Analysis records symbol, decision time, session, quote, spread, source,
snapshot and manifest bindings, timeframe coverage, freshness/QC, market regime,
volatility, event-risk state, software versions, and integrity tier.

### 5.2 Analysis View

A View preserves one system's original interpretation:

- source type (`ZENITH` or `EXTERNAL`);
- engine/model/prompt/configuration fingerprint;
- market bias and calibrated confidence, when available;
- primary and alternative scenarios;
- zones, liquidity, waits, prohibitions, invalidations, and expiry;
- declared action: `SETUP`, `WATCH`, `WAIT`, `HOLD`, `REJECT`, or `ABSTAIN`.

A Comparison references views; it never rewrites them. This prevents hindsight
contamination and makes disagreements auditable.

### 5.3 Decision

Every scorable conclusion becomes a separate Decision. Each Decision declares:

- decision type and direction;
- activation conditions and reference price;
- evaluation horizons;
- measurable success and failure criteria;
- invalidation and expiry;
- dependencies on other decisions;
- prohibited inference or data;
- candidate and semantic-opportunity identity when applicable.

A conclusion without measurable criteria is `NON_SCORABLE`. It remains visible
for coverage auditing but is excluded from accuracy and edge metrics.

### 5.4 Outcome accounts

`MODEL_OUTCOME` measures the frozen analysis or setup against standardized market
prices regardless of whether the user traded it.

`MANUAL_TRADE_OUTCOME` measures a user-confirmed execution and may include actual
entry, exit, spread, slippage, partial closes, and timing. A manual trade may
reference a model setup, but it never replaces the model outcome.

## 6. Lifecycles

Analysis and outcome evaluation follow:

```text
RECORDED -> VALIDATED -> FOLLOWUP_PENDING -> PARTIALLY_OBSERVED -> RESOLVED
```

Exceptional states are `VALIDATION_FAILED`, `UNRESOLVABLE`, `SUPERSEDED`, and
`CORRECTION_APPENDED`.

Candidate lifecycle and outcome lifecycle remain independent. A Candidate may be
`SUPPRESSED` while its previously frozen directional or setup decision continues
to receive follow-up. `SUPPRESSED` with `cause_status=UNKNOWN` is not silently
converted into expired, invalidated, or superseded.

## 7. Evaluation rules

### 7.1 Directional forecasts

Each horizon resolves to `CORRECT`, `INCORRECT`, `NEUTRAL`, `AMBIGUOUS`, or
`INSUFFICIENT_FOLLOWUP`. Policy uses direction return, favorable/adverse
excursion, and ATR-normalized thresholds so low-volatility noise is not counted
as accuracy.

### 7.2 Scenarios

Scenarios are evaluated as ordered paths: activation, required events,
invalidation precedence, event order, and expiry. Outcomes are `CONFIRMED`,
`PARTIALLY_CONFIRMED`, `INVALIDATED`, `EXPIRED_UNTRIGGERED`, or `UNRESOLVED`.
Primary and alternative scenarios are scored separately; an alternative outcome
does not retroactively make the primary scenario correct.

### 7.3 Entry setups

Closed-bar, bid/ask-aware labeling measures entry touch, TP/SL precedence, MFE,
MAE, realized R, worst-realistic-fill R, time to entry, time to outcome, and
expiry. Labels are `TP_FIRST`, `SL_FIRST`, `ENTRY_NOT_TRIGGERED`,
`EXPIRED_UNTRIGGERED`, `AMBIGUOUS_SAME_BAR`, or `UNRESOLVED`.

### 7.4 WAIT and HOLD

Counterfactual labels require a decision-time frozen candidate or control. Labels
include `PROTECTED_FROM_LOSS`, `MISSED_WINNER`, `CORRECT_PATIENCE`,
`UNNECESSARY_DELAY`, `NO_MATERIAL_OPPORTUNITY`, and `NOT_SCORABLE`. The registry
must never synthesize a retrospective setup from the revealed chart.

### 7.5 REJECT and filters

Filter evaluation measures loss avoidance, winner rejection, accepted-versus-
rejected expectancy, filter lift, opportunity cost, and unknown/suppressed rates.
Without frozen pre-rejection geometry, only coverage is reported.

### 7.6 Comparisons

Zenith, External, baselines, and software versions are compared only on matched
symbol, decision-time market evidence, horizon, and cohort. An omitted opinion is
`ABSTAIN`, not an automatic win or loss.

## 8. Metrics and reporting

### 8.1 Coverage report

Coverage precedes performance. It reports counts by integrity tier, source class,
resolved/pending/unresolvable outcome, timeframe coverage, unknown lifecycle,
missing outcome, and audit error. Failed coverage forces
`INSUFFICIENT_EVIDENCE` on performance conclusions.

### 8.2 Performance report

Reports slice by system, symbol, trade style, horizon, regime, volatility,
direction, decision type, and engine/policy version. Metrics include:

- directional accuracy and coverage;
- scenario confirmation and invalidation rates;
- TP-first/SL-first rates and trigger rate;
- expectancy R, profit factor, MFE, and MAE;
- missed-winner and loss-avoidance rates;
- filter lift and abstention quality;
- maximum drawdown proxy;
- calibration error only when calibrated probabilities exist.

Every rate displays numerator, denominator, unresolved count, cohort identity,
and confidence/uncertainty information appropriate to the sample. Headline
metrics use only eligible `VERIFIED` records.

### 8.3 Comparison and failure reports

Comparison reports show aggregate results and paired differences for matched
cohorts. Failure analysis groups direction, location, timing, geometry, excessive
filtering, regime mismatch, unexplained disappearance, ambiguous scenarios, and
data/lifecycle defects. Failure reports inform proposals but cannot mutate policy.

### 8.4 Dashboard states

Dashboard readiness is explicit:

```text
DATA_NOT_READY
COLLECTING
PRELIMINARY
VALIDATION_READY
FORWARD_VALIDATED
EDGE_NOT_VALIDATED
REGRESSION_DETECTED
```

Every aggregate supports drill-down to immutable events and source evidence.

## 9. Upgrade governance

An upgrade gate requires:

- valid schemas, hashes, and evidence bindings;
- no future leakage;
- unknown lifecycle below the versioned threshold;
- minimum independent and resolved observations;
- development, validation, and forward cohorts kept separate;
- no safety or drawdown regression against the current version;
- improvement in declared primary metrics on matched cohorts;
- no severe deterioration in critical regimes;
- manual review and approval.

Gate decisions are `REJECT`, `CONTINUE_COLLECTION`, `SHADOW_ONLY`, or
`PROMOTE_FOR_MANUAL_VALIDATION`. Promotion never enables auto-execution.

Exact sample thresholds and statistical tests are policy configuration, not
hard-coded claims in this design. Until configured and satisfied, the status
remains `EDGE_NOT_VALIDATED`.

## 10. Validation and failure handling

Invalid input is quarantined, retained, and excluded from headline metrics with
a deterministic reason such as `SCHEMA_INVALID`, `MISSING_EVIDENCE`,
`HASH_MISMATCH`, `DECISION_TIME_AMBIGUOUS`, `FUTURE_DATA_DETECTED`,
`DUPLICATE_EVENT`, `BROKEN_HASH_CHAIN`, `OUTCOME_POLICY_MISMATCH`, or
`SOURCE_CLASS_UNKNOWN`.

A failed SQLite rebuild cannot damage the ledger. Re-scoring creates a new score
version rather than overwriting old results.

Required tests include schema contracts, hash-chain integrity, idempotent
ingestion, future-leakage rejection, closed-bar labeling, same-bar ambiguity,
bid/ask and spread behavior, semantic candidate deduplication, WAIT/HOLD
counterfactuals, migration classification, SQLite rebuild parity, matched-cohort
comparison, and safety assertions. Golden fixtures cover known cases;
property-based tests cover event and price sequences.

## 11. Historical migration

A read-only scanner inventories existing outputs, fingerprints source artifacts,
matches snapshots/decisions/manifests, emits migration events to the new ledger,
and produces a coverage report. It does not alter the scanned artifacts.

Migration tiers are:

- `VERIFIED`: decision time and required evidence bindings are complete;
- `PARTIAL`: only some required bindings are available;
- `CHAT_ONLY`: only conversation text or an unstable chat reference exists;
- `UNMATCHED`: an artifact exists but cannot be reliably associated with an
  analysis.

Only `VERIFIED` records are eligible for headline metrics. Other tiers remain
available for exploratory and coverage analysis.

## 12. Delivery phases

### Phase 1: Registry Foundation

Deliver schemas, the append-only ledger, stable IDs, Zenith ingestion, integrity
verification, and the rebuildable SQLite index.

### Phase 2: Outcome Evaluation

Deliver horizon scheduling; direction, scenario, and setup labelers; model/manual
outcome separation; WAIT/HOLD/REJECT evaluation; and core performance reports.

### Phase 3: Comparison and Migration

Deliver External and Comparison ingestion, matched cohorts, historical import,
coverage reporting, and failure analysis.

### Phase 4: Upgrade Governance

Deliver dashboard projections, version comparisons, regression detection,
upgrade gates, and immutable audit bundles.

## 13. Acceptance criteria

The registry is operationally complete when:

1. Every new eligible analysis receives an `analysis_id` and evidence binding.
2. Zenith, External, and Comparison records remain independently attributable.
3. Every scorable decision has an outcome or an explicit unresolved reason.
4. SQLite can be rebuilt deterministically from the ledger.
5. Every metric drills down to registry events and source evidence.
6. Incomplete evidence cannot enter headline statistics.
7. Existing evidence and historical outputs remain unchanged.
8. Re-ingestion is idempotent and corrections remain append-only.
9. Source classes and development/validation/forward cohorts never mix silently.
10. Safety validation confirms zero broker writes and zero Permission leakage.

## 14. Implementation boundary

The first implementation plan will cover Phase 1 only. Later phases depend on
the stable registry contract and receive separate implementation checkpoints.
This keeps the first delivery reviewable and prevents outcome or dashboard scope
from destabilizing the evidence foundation.
