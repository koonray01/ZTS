# Analysis Registry Phase 2 Full-Loop Design

## Objective

Complete the existing Analysis Performance Registry Phase 2 runtime loop so
new Zenith and Chat Model predictions can be frozen before their outcomes,
scheduled, evaluated against source-bound follow-up evidence, and reported
without hindsight reconstruction. Preserve the append-only canonical history,
Manual Only safety, and strict separation from Part 3 and broker state.

This work completes measurement infrastructure. It does not demonstrate a
trading edge, tune policy, promote research, place orders, or run a persistent
background service.

## Observed Runtime Gap

The Phase 2 architecture and deterministic labelers exist, but the canonical
runtime did not produce representative outcome coverage at the review
baseline (`2026-07-23T03:11:59Z`, ledger head
`5f7770107a4d55b72aa82dfd9d46ffd7c549b09d338572e1f5287b61f1ac8007`):

- 44 frozen decisions produced one evaluation job and zero model outcomes;
- the sole due job is pending because its source binding is incomplete;
- Zenith scenarios and Candidates do not consistently provide scheduler-ready
  horizons, expiry, reference, ATR, event grammar, or setup geometry;
- catch-up reports a failure count but suppresses per-job reason details;
- analyses launched into separate output directories do not preserve a useful
  previous-snapshot Candidate lifecycle;
- performance reports therefore return `INSUFFICIENT_EVIDENCE`.

These are runtime integration and evidence-coverage gaps, not proof that the
existing labelers or storage architecture are invalid.

## Selected Architecture

Add `Phase2DecisionNormalizer` in
`src/ctl_analysis_registry/normalizer.py` as one boundary between analysis
outputs and the existing Registry recorder:

```text
Zenith / Chat output
        |
        v
Phase2DecisionNormalizer
        |
        v
Scorable contract validation
        |
        v
Freeze decision -> Schedule jobs
        |
        v
Foreground or manual catch-up
        |
        v
Follow-up evidence -> Outcome label -> Reports
```

The normalizer is the only component that translates runtime analysis objects
into Phase 2 decision contracts. The ledger, SQLite projection, canonical path
resolver, and writer coordination remain the existing authoritative
mechanisms. Existing deterministic labelers remain authoritative where their
frozen contract is unchanged; the Setup range contract and Scenario
terminalization use the explicitly versioned additions defined below.

All native decisions produced after cutover record
`normalization_policy_version=PHASE2_NORMALIZATION_V1`. Older decisions never
receive that version through inference or projection rebuild.

## Prediction Contracts

The normalizer emits one of four decision types:

### Directional

Requires:

- binary direction (`BULLISH` or `BEARISH`);
- decision-time reference price and ATR, or a frozen conditional activation;
- declared profile, timeframe scope, horizons, and headline horizon;
- labeling policy `DIRECTIONAL_TERMINAL_ATR_V1`;
- complete source and evidence binding.

Outcome uses signed terminal return in ATR units, plus MFE and MAE.

Zenith must emit an explicit deterministic `directional_claims` collection.
Each claim declares its direction, profile, timeframe scope, reference or
activation, ATR policy, and horizons. The normalizer never derives a
Directional decision from a Primary Scenario, action-plan prose, Candidate, or
Chat narrative. If the collection is absent or empty, no Zenith Directional
decision or job is created.

The deterministic engine, not the normalizer, owns claim emission under
`DIRECTIONAL_CLAIM_EMISSION_V1`. A claim may be emitted only from a finalized
binary engine state (`BULLISH` or `BEARISH`) with a frozen evaluation
timeframe, decision-time reference price, ATR value and ATR timeframe,
profile, horizons, and source binding. Neutral, mixed, pending, or
insufficient-data states emit no claim; they are coverage observations, not
predictions. Conditional claims are permitted only when the engine emits the
complete numeric activation contract before the outcome.

Claim identity is
`system | symbol | profile | evaluation_timeframe | claim_family_id |
direction | emission_policy_version`. `claim_family_id` is emitted by the
engine and remains stable for the same thesis across sessions. An identical
pre-activation claim is `unchanged`; a material change to direction,
activation, reference, ATR policy, timeframe, horizon policy, or source thesis
creates a new decision linked as a revision. Once evaluation has started, a
later claim is always a new decision and cannot alter the original score.

Every native engine run also emits a deterministic
`prediction_emission_manifest`, even when it emits no prediction. The manifest
lists every prediction family enabled for that engine/profile, its emission
policy version, and exactly one status:

- `EMITTED`, with the resulting decision IDs;
- `ABSTAINED_BY_POLICY`, with a machine-readable neutral, mixed, pending, or
  insufficient-data reason;
- `NOT_APPLICABLE`, with a machine-readable capability reason;
- `EMISSION_FAILED`, with a sanitized diagnostic.

The manifest is frozen and source-bound with the analysis in one typed
`PREDICTION_EMISSION_RECORDED` event whose stable identity is derived from the
analysis run ID, engine, profile, and emission-policy version. An absent
enabled family, missing manifest, or `EMISSION_FAILED` is an integration
failure, not an empty denominator. `ABSTAINED_BY_POLICY` and valid
`NOT_APPLICABLE` entries remain coverage observations and do not create
predictions.

### Scenario

Requires:

- ordered machine-readable event steps;
- invalidation grammar;
- expiry time;
- horizons and headline horizon;
- evidence and source binding.

Outcome records confirmation, invalidation, expiry, completion ratio, and
completed event steps using `ORDERED_SCENARIO_V1`.

Runtime scenario names are not directly scorable grammar. The normalizer
accepts only this deterministic translation:

| Runtime event | Canonical event | Required frozen geometry |
|---|---|---|
| `BREAK_BULLISH` | `CLOSED_ABOVE` | timeframe and numeric level |
| `BREAK_BEARISH` | `CLOSED_BELOW` | timeframe and numeric level |
| `RETEST_HOLD` bullish | `ENTERED_BAND` then `CLOSED_ABOVE` | retest lower/upper band and hold level |
| `RETEST_HOLD` bearish | `ENTERED_BAND` then `CLOSED_BELOW` | retest lower/upper band and hold level |
| `CONTINUATION` bullish | `CLOSED_ABOVE` | timeframe and continuation level |
| `CONTINUATION` bearish | `CLOSED_BELOW` | timeframe and continuation level |
| scenario invalidation | `INVALIDATION_HIT` | side-aware numeric condition |

One runtime `RETEST_HOLD` expands into two ordered canonical steps. Events with
missing direction, timeframe, or numeric geometry are
`NON_SCORABLE/SCENARIO_EVENT_GEOMETRY_MISSING`. Unknown event names are
`NON_SCORABLE/SCENARIO_EVENT_UNSUPPORTED`; the normalizer never guesses a
translation.

### Setup

Requires:

- side-aware entry geometry;
- stop and exactly one scoring target;
- expiry time and horizon;
- trigger or activation contract;
- evidence and source binding.

Outcome uses `SINGLE_TARGET` and bid/ask-aware path evaluation. Additional
targets are diagnostic milestones and do not create headline predictions.

This range contract is evaluated by the new versioned policy
`RANGE_ACTIVATION_SINGLE_TARGET_V2`; the existing scalar Setup labeler remains
available only for decisions frozen under its older policy. V2 follow-up
evidence must contain ordered timestamped bid/ask observations spanning
activation through expiry. Bar-only evidence or observations without the
required side of quote cannot prove an in-range executable touch and resolve
as `AMBIGUOUS/EVIDENCE_GRANULARITY_INSUFFICIENT`, never by scalar-threshold
fallback.

Zenith Candidates currently expose an `entry_range`; Phase 2 freezes one
conservative scoring entry before the outcome:

- BUY scoring entry is the range upper bound;
- SELL scoring entry is the range lower bound;
- evaluation begins only after the frozen Candidate trigger/activation is
  satisfied;
- after activation, BUY enters only on a recorded quote satisfying
  `entry_lower <= ask <= entry_upper`;
- after activation, SELL enters only on a recorded quote satisfying
  `entry_lower <= bid <= entry_upper`;
- after activation, consecutive BUY observations where the earlier ask is
  above `entry_upper` and the later ask is below `entry_lower`, with no
  intervening recorded ask inside the range, are
  `GAP_THROUGH_UNRESOLVED`;
- after activation, consecutive SELL observations where the earlier bid is
  below `entry_lower` and the later bid is above `entry_upper`, with no
  intervening recorded bid inside the range, are
  `GAP_THROUGH_UNRESOLVED`;
- movement beyond the favorable side before activation never counts as an
  entry or a gap-through;
- contact with either inclusive range boundary after activation counts as an
  executable range touch, while RR and realized R still use the frozen
  conservative scoring entry;
- midpoint, best-price, and hindsight-selected entries are prohibited.

The original range, conservative scoring entry, scoring method, and trigger
remain in the frozen decision. RR and realized R use the conservative scoring
entry.

### Abstention

Only a deterministic Candidate that already has complete entry range, trigger,
side, stop, exactly one scoring target, profile, source binding, and expiry may
produce a scorable abstention control. Before any outcome is observed, the
Candidate engine must freeze a `WAIT`, `REJECT`, or `WITHHELD` disposition and
a machine-readable abstention reason. The paired control copies the
Candidate's geometry, trigger, scoring-entry policy, expiry, opportunity
identity, and source binding; it also links the source Candidate decision and
the frozen abstention reason.

Generic `HOLD`, `WAIT`, and `NO_SETUP` output without such a complete
Candidate produces no control and remains `NON_SCORABLE`. When several
variants belong to one opportunity, exactly one control is selected before
outcome observation using the same representative priority as Setup reporting:
`FULL_CONFIRMATION`, then `EARLY_CONFIRMATION`, then `CONTINUATION`, then
lexical stable decision ID. Control creation after activation, entry, expiry,
or any outcome evidence is prohibited.

The paired frozen control produces one of:

- `PROTECTED_FROM_LOSS`;
- `MISSED_WINNER`;
- `CORRECT_PATIENCE`;
- `UNNECESSARY_DELAY`;
- `NO_MATERIAL_OPPORTUNITY`.

## Profile and Horizon Policy

Use fixed ISO-8601 durations:

| Profile | Diagnostic horizons | Headline horizon |
|---|---|---|
| Scalping | `PT15M`, `PT1H` | `PT1H` |
| Daytrade | `PT4H`, `P1D` | `P1D` |

Every decision records its profile and headline horizon. Reports compare only
like-for-like cohorts. Changing a horizon policy requires a new policy version
and never rewrites existing decisions.

Scheduling is decision-type aware:

- Directional jobs close at each fixed horizon.
- Scenario jobs close at confirmation, invalidation, or frozen scenario
  expiry; horizons provide reporting checkpoints but never extend expiry.
- Setup jobs observe from activation through frozen setup expiry; diagnostic
  horizons cannot extend the setup lifetime.
- Abstention controls use the paired setup activation and expiry.

Directional decisions have one outcome per declared horizon. Scenario
decisions have exactly one terminal outcome per decision and policy version;
diagnostic-horizon jobs append checkpoint evidence only and never append a
second Scenario outcome.

Confirmation, invalidation, or expiry appends one typed
`SCENARIO_TERMINALIZED` aggregate event. Its payload contains the complete
terminal outcome, outcome ID, terminal evidence hash, terminal reason, and the
stable IDs of every remaining checkpoint job with their
`CANCELLED_TERMINAL` state. No separate `MODEL_OUTCOME_RECORDED` or
`EVALUATION_JOB_STATE_CHANGED` event is appended for that same terminal
operation. The projection applies the single event in one SQLite transaction,
deriving the outcome row and all job-state rows together. After a crash, replay
therefore sees either no terminal event or the complete aggregate; it cannot
observe a partial terminalization. A checkpoint processed before the terminal
event remains immutable diagnostic evidence. The stable aggregate event,
outcome, and job IDs make reruns no-ops.

## Source Binding

Every native live scorable decision freezes:

- snapshot ID and immutable manifest hash;
- evidence hashes;
- source class and MT5 server;
- symbol, digits, and point;
- broker UTC offset;
- overlap fingerprint;
- decision time and freshness/QC status.

Source binding comes from the validated snapshot/evidence bundle, not from
later environment defaults. Missing native fields make the decision
`NON_SCORABLE` with `SOURCE_BINDING_INCOMPLETE`.

Follow-up collection must prove that the later MT5 evidence matches the frozen
source binding before labeling. Mismatch becomes `SOURCE_MISMATCH`; conflicting
evidence becomes `AMBIGUOUS`.

The overlap fingerprint is the SHA-256 of canonical JSON containing the last
three closed bars at or before decision time on the decision's evaluation
timeframe. Each bar contributes server, symbol, timeframe, open time, close
time, OHLC, and tick volume. Follow-up history must reproduce the same three
bars before later bars are accepted. Fewer than three closed bars makes the
native decision non-scorable. The validated MT5 adapter, not the normalizer,
must supply server, symbol specification, broker offset, and these bars in the
snapshot evidence bundle.

## Runtime Data Flow

For each current analysis:

1. Capture a fresh `LIVE_MT5` snapshot and validate connection, freshness, QC,
   locks, and zero-write safety.
2. Produce deterministic Zenith output and any separately attributable Chat
   Model envelope.
3. Normalize every claim and assign scorable or non-scorable reason codes.
4. Freeze all decisions before any outcome observation.
5. Schedule jobs only for scorable decisions, using stable identities.
6. Append events and rebuild the projection idempotently.
7. Run bounded foreground catch-up for due jobs.
8. Report decision counts, scorable counts, scheduled jobs, resolved outcomes,
   remaining jobs, failures by reason, and safety counters.

Normal analysis does not wait indefinitely for catch-up and does not start a
daemon.

Chat Model support in this delivery includes one structured operator boundary
that validates and registers a `CHAT_MODEL` envelope through the same
normalizer. The public function is
`normalize_chat_envelope(envelope, snapshot, profile)` and the operator CLI is
`tools/register_chat_analysis.py`. If the active environment cannot call that
boundary, the response is `CHAT_REGISTRATION_BLOCKED`; Chat coverage is
reported independently and does not block Zenith Phase 2 acceptance. The
Zenith launcher is never represented as accepting Chat envelopes.

## Manual Catch-Up and Audit

An explicit operator command processes canonical due jobs in bounded batches.
It uses the same `run_catchup` path as foreground analysis. The command:

- acquires the canonical writer lease;
- processes jobs ordered by `due_at` and stable ID;
- stores immutable follow-up evidence before an outcome;
- labels each job once;
- persists retry/terminal state and reason codes;
- can be rerun without duplicate jobs, evidence, or outcomes;
- reports processed, resolved, retried, terminalized, failed, and remaining
  counts.

Foreground and manual execution must produce identical outcomes from identical
evidence.

## Failure and Retry Policy

- `SOURCE_BINDING_INCOMPLETE`: native decision is non-scorable; no job.
- `UNRESOLVED_SOURCE_BINDING`: legacy job cannot be safely evaluated and is
  terminalized without an outcome.
- `SOURCE_MISMATCH`: follow-up source differs from the frozen binding.
- `INSUFFICIENT_FOLLOWUP`: required historical evidence remains unavailable
  after bounded retries.
- `AMBIGUOUS`: evidence supports no deterministic ordering or conflicts.
- `DEFERRED`: another canonical writer owns the lease.
- `PARTIAL`: some bounded jobs completed while others retried or terminalized.
- `REGISTRY_BLOCKED`: recording failed; analysis may still be shown but audit
  continuity is not claimed.

Catch-up must never swallow an exception. Each failed job persists a stable
reason code, diagnostic summary, attempt count, last-attempt time, and terminal
or next-retry state. Raw stack traces and secrets do not enter the ledger.

Job-state durability uses a new typed append-only
`EVALUATION_JOB_STATE_CHANGED` event. It records the job ID, from/to state,
reason code, sanitized diagnostic, attempt count, attempted time, and next
retry time when applicable. Projection rebuild applies these events in ledger
order. SQLite is never the sole source of retry or terminal state.

`PREDICTION_EMISSION_RECORDED`, `OPPORTUNITY_VARIANT_SET_FROZEN`,
`EVALUATION_JOB_STATE_CHANGED`, `SCENARIO_TERMINALIZED`,
`LEGACY_RECORD_CLASSIFIED`, and `NORMALIZATION_POLICY_STATE_CHANGED` are
backward-compatible additions to the Phase 2 event-type dispatch and JSON
schemas. Existing events remain readable without migration. Unknown new event
versions fail validation rather than being ignored.

## Legacy Policy

Existing frozen events remain immutable.

- Decisions without a complete Phase 2 contract become
  `LEGACY_UNSCORABLE`.
- The current incomplete pending job becomes
  `UNRESOLVED_SOURCE_BINDING` after conservative migration classification.
- No missing price, ATR, trigger, horizon, expiry, or binding is reconstructed
  from post-outcome knowledge.
- Legacy records use a separate `LEGACY` cohort and never enter headline
  performance.
- Native post-cutover records use `NATIVE_PHASE2`.

Migration is append-only classification plus a rebuildable projection update;
it does not edit or delete historical ledger events.

Legacy durability uses a typed `LEGACY_RECORD_CLASSIFIED` event with a stable
identity derived from the original event or job ID, classification, reason
codes, and cohort. Re-running migration appends nothing when the classification
already exists. The projection derives legacy state only from these events.

## Candidate Lifecycle

Candidate identity and lifecycle must resolve across sessions and output
directories through the canonical Registry, not an output-local predecessor.
Each new analysis may classify an existing semantic Candidate as:

- unchanged;
- revised before evaluation start;
- superseded;
- invalidated;
- expired;
- activated;
- terminal.

A material revision receives a new decision identity and links to the original.
Late changes are audit-only corrections and cannot change scoring.

The semantic Candidate namespace is:

`system | symbol | profile | timeframe | semantic_opportunity_id |
opportunity_generation_id | side`

`semantic_opportunity_id` must be emitted by the deterministic Candidate
engine. Falling back to a snapshot-local `candidate_id` makes the Candidate
non-linkable across sessions and therefore non-scorable for lifecycle metrics.
Entry variants (`EARLY_CONFIRMATION`, `FULL_CONFIRMATION`, `CONTINUATION`) are
separate decisions under one prediction family and one opportunity generation;
reports deduplicate variants within that generation before headline setup
metrics.

`opportunity_generation_id` is emitted by the deterministic Candidate engine
and is the stable hash of the semantic opportunity ID, side, profile,
timeframe, material thesis fields, and Candidate policy version. Identical
material inputs across sessions reproduce the same generation ID; a material
revision produces a new one. The frozen variant-set event identity includes
this generation ID.

If a new generation appears before evaluation starts, the lifecycle resolver
terminalizes the predecessor as `SUPERSEDED_PRE_EVALUATION`; the predecessor
is audit-visible but headline-ineligible. If evaluation has started, the
predecessor remains immutable and the new generation is a separate
time-stamped prediction; both are headline-eligible as distinct forward
predictions. Reports never collapse generations by `semantic_opportunity_id`
alone and never count more than one representative within a generation.

The Candidate engine must emit the complete variant manifest for an
opportunity generation with `variant_set_complete=true` before the normalizer
schedules any Setup or Abstention-control job. The Registry freezes that
manifest in an `OPPORTUNITY_VARIANT_SET_FROZEN` event and selects the
representative from that sealed set using the fixed priority below. A variant
that appears after sealing cannot join the generation; it creates a new
generation linked as a material revision. Missing or incomplete manifests are
`NON_SCORABLE/VARIANT_SET_INCOMPLETE`. This makes representative selection
independent of session and registration arrival order.

For each analysis the lifecycle resolver queries all nonterminal Candidates in
the canonical Registry for the same namespace. Exact material fields
(activation, entry range, scoring entry, stop, target, expiry, direction, and
policy version) determine `unchanged` versus `revised`. Absence from a new
fresh snapshot does not by itself mean invalidation: an explicit deterministic
invalidation, expiry, supersession, or terminal event is required. Otherwise
the prior Candidate remains unresolved and is flagged
`LIFECYCLE_EVIDENCE_MISSING`.

## Reporting

Coverage and performance reports separate:

- `ZENITH` and `CHAT_MODEL`;
- Scalping and Daytrade;
- prediction type;
- headline horizon;
- regime and volatility;
- `NATIVE_PHASE2` and `LEGACY`.

Reports expose:

- frozen, scorable, non-scorable, scheduled, due, resolved, and terminal counts;
- non-scorable and failure reason distributions;
- directional accuracy, neutral rate, signed ATR return, MFE, and MAE;
- scenario confirmation/invalidation/expiry and completion ratios;
- setup trigger rate, TP/SL ordering, ambiguity rate, and realized R;
- abstention control outcomes;
- sample size and evidence coverage.

Only the configured headline horizon contributes to headline accuracy or
expectancy. Diagnostic horizons are displayed separately. Setup variants are
shown individually for diagnostics but count once per semantic opportunity
using this frozen representative priority:
`FULL_CONFIRMATION`, then `EARLY_CONFIRMATION`, then `CONTINUATION`, then
lexicographically smallest stable variant ID. The selected representative is
stored when the opportunity variant set is sealed and cannot change after job
scheduling or outcome evidence.

Capability, coverage, and efficacy are independent. Until forward sample sizes
are sufficient, the headline remains `INSUFFICIENT_EVIDENCE`.
`validated_edge=false`, `policy_tuned=false`, and
`promotion_gate_open=false` remain mandatory in Phase 2.

## Safety and Non-Goals

- `trade_write_enabled=false`;
- `auto_execution_enabled=false`;
- `order_actions=0`;
- `permission_leakage=0`;
- no broker placement, modification, cancellation, or close;
- no automatic Part 3;
- no persistent background service;
- no automatic policy tuning or promotion;
- no use of model outcomes as trade outcomes;
- no hindsight repair of legacy predictions.

## Verification Strategy

Tests cover:

- normalizer contracts and reason codes for all four decision types;
- profile horizon and headline-horizon mapping;
- complete source binding from a real-shaped LIVE_MT5 fixture;
- job creation for every scorable decision and none for non-scorable records;
- deterministic follow-up and labels for Directional, Scenario, Setup, and
  Abstention;
- bounded retry and terminal failure persistence;
- foreground/manual catch-up parity;
- restart, rebuild, and idempotency;
- legacy quarantine and exclusion from headline metrics;
- Candidate lifecycle across output directories and sessions;
- canonical path and concurrent-writer behavior;
- failure diagnostics without sensitive data;
- all zero-write and Permission invariants.
- scalar conservative scoring-entry derivation from BUY and SELL ranges;
- gap-through and partial-touch behavior;
- exact scenario-event translation and unsupported grammar rejection;
- explicit Directional claims without Scenario-derived double counting;
- Directional emission-state filtering, family identity, and revision rules;
- abstention-control eligibility, pre-outcome freezing, source linkage, and
  deterministic representative selection;
- single Scenario terminal outcome with checkpoint cancellation and rerun
  idempotency;
- aggregate Scenario terminal-event replay with crash injection before and
  after the ledger append;
- Setup V2 ordered bid/ask evidence, activation gating, range touch,
  insufficient granularity, and no scalar fallback;
- sealed opportunity variant sets presented in different arrival orders;
- cross-generation reporting for pre-evaluation supersession and
  post-evaluation revision;
- policy-disabled job quarantine and explicit resume behavior;
- emission-manifest completeness and zero-emission integration failure;
- replay of job-state and legacy-classification events after projection
  deletion;
- structured Chat registration and blocked-capability behavior.

Use synthetic and replay registries for destructive tests. The canonical live
Registry receives only an append-only migration classification after dry-run
counts and hashes match.

## Shadow Cutover and Rollback

Cutover is an explicit operator action, not a side effect of analysis:

1. Copy the canonical ledger and required immutable evidence to an isolated
   replay Registry; record that immutable copy's `shadow_source_head` and event
   counts.
2. Rebuild the replay projection, run legacy classification and
   `PHASE2_NORMALIZATION_V1` in dry-run mode, and prove that dry-run writes
   nothing to the canonical Registry.
3. Run a shadow cohort in which V1 produces proposed decisions, jobs, reason
   codes, and outcomes only in the isolated Registry. Compare ledger/projection
   reconciliation, decision and job counts, stable IDs, reason-code
   distributions, outcome hashes, safety counters, and foreground/manual
   parity against the acceptance fixtures and current read-only baseline.
4. Treat the replay head after shadow writes as a separate `shadow_result_head`;
   it is expected to differ from `shadow_source_head` and is never used as the
   canonical concurrency check.
5. To cut over, acquire the canonical writer lease and perform one
   compare-and-append operation: enable only if the current canonical head
   still equals `shadow_source_head`, then append the enable event before
   releasing the lease. A mismatch aborts with `SHADOW_BASE_STALE` and requires
   a new shadow run from the new canonical head.
6. Cut over only when all required comparisons pass and the operator explicitly
   enables `PHASE2_NORMALIZATION_V1`.
7. After cutover, complete at least one native `LIVE_MT5` forward outcome
   before declaring Phase 2 operationally complete.

Rollback disables new V1 normalization and scheduling through the same
versioned feature gate. It never deletes, edits, or hides decisions, jobs,
state changes, evidence, classifications, or outcomes already appended.
Projection rebuild remains compatible with those events, and pending V1 jobs
remain visible for explicit manual terminalization or resumption after review.
Re-enabling V1 with the same policy version and stable inputs is idempotent;
semantic changes require a new policy version and a new shadow cutover.

Foreground and ordinary manual catch-up select jobs only when their frozen
normalization policy is currently `ENABLED`. On disable, pending V1 jobs derive
`PAUSED_POLICY_DISABLED` from the policy event and are excluded before evidence
collection or labeling; they do not consume retry attempts. An explicit audit
command may terminalize selected paused jobs with an append-only state event.
Re-enable resumes the remaining paused jobs from their prior durable state.

Enable and disable actions append a typed
`NORMALIZATION_POLICY_STATE_CHANGED` event containing the policy version,
`ENABLED` or `DISABLED`, operator-command timestamp, shadow Registry identity,
shadow ledger head, canonical source head used by the shadow run, comparison
summary hash, and reason. The canonical projection derives the active policy
only from the latest valid event in ledger order; a local config flag alone
cannot activate normalization. Repeating the same transition with the same
policy, source head, and comparison hash appends nothing.

## Acceptance Gates

Phase 2 is operationally complete when:

1. Every normalized supported prediction is frozen with a scorable status and
   reason. The denominator excludes policy-abstained claims and unsupported
   inputs recorded as non-scorable, but it never excludes an enabled family
   missing from its emission manifest or marked `EMISSION_FAILED`; either
   condition fails acceptance.
2. Scorable decisions create stable evaluation jobs 100% of the time.
3. Native live scorable jobs have complete source bindings 100% of the time.
4. Fixture and replay shadow cohorts produce at least one end-to-end outcome
   for Directional, Scenario, Setup, and Abstention.
5. Foreground and manual catch-up produce identical results.
6. Restart and projection rebuild create no duplicate job or outcome.
7. Legacy records are classified and excluded from headline metrics.
8. Reports reconcile exactly with ledger and projection counts.
9. All sessions and worktrees resolve the same canonical Registry.
10. All safety counters remain zero.
11. Focused tests, the full suite, integrated validation, contract validation,
    and Phase 2 acceptance audit pass.
12. No acceptance result is represented as predictive or trading edge.
13. A native `LIVE_MT5` forward decision completes decision -> job ->
    follow-up -> outcome with complete binding and no manual repair.
14. Missing real Setup or Abstention opportunities remain an explicit coverage
    gap; no Candidate or control is manufactured to satisfy acceptance.
15. Shadow mode performs zero canonical writes, cutover records its source
    ledger head and policy version, and rollback preserves a fully rebuildable
    append-only history.
16. A representative native-run cohort has a complete emission manifest for
    every enabled Zenith prediction family, zero `EMISSION_FAILED` entries, and
    at least one native Directional decision completing its headline outcome.

Production efficacy remains a later evidence milestone. Phase 2 completion
means trustworthy measurement, not favorable performance.
