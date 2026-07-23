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
runtime does not yet produce representative outcome coverage:

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

Add one `Phase2DecisionNormalizer` boundary between analysis outputs and the
existing Registry recorder:

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
into Phase 2 decision contracts. The ledger, SQLite projection, deterministic
labelers, canonical path resolver, and writer coordination remain the existing
authoritative mechanisms.

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

### Scenario

Requires:

- ordered machine-readable event steps;
- invalidation grammar;
- expiry time;
- horizons and headline horizon;
- evidence and source binding.

Outcome records confirmation, invalidation, expiry, completion ratio, and
completed event steps using `ORDERED_SCENARIO_V1`.

### Setup

Requires:

- side-aware entry geometry;
- stop and exactly one scoring target;
- expiry time and horizon;
- trigger or activation contract;
- evidence and source binding.

Outcome uses `SINGLE_TARGET` and bid/ask-aware path evaluation. Additional
targets are diagnostic milestones and do not create headline predictions.

### Abstention

Only a rejected or withheld setup with frozen entry, stop, scoring target, and
expiry is scorable. Generic `HOLD`, `WAIT`, and `NO_SETUP` records remain in
the audit trail but are `NON_SCORABLE`.

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

Use synthetic and replay registries for destructive tests. The canonical live
Registry receives only an append-only migration classification after dry-run
counts and hashes match.

## Acceptance Gates

Phase 2 is operationally complete when:

1. Every new supported prediction is frozen with a scorable status and reason.
2. Scorable decisions create stable evaluation jobs 100% of the time.
3. Native live scorable jobs have complete source bindings 100% of the time.
4. A shadow cohort produces at least one end-to-end outcome for Directional,
   Scenario, Setup, and Abstention.
5. Foreground and manual catch-up produce identical results.
6. Restart and projection rebuild create no duplicate job or outcome.
7. Legacy records are classified and excluded from headline metrics.
8. Reports reconcile exactly with ledger and projection counts.
9. All sessions and worktrees resolve the same canonical Registry.
10. All safety counters remain zero.
11. Focused tests, the full suite, integrated validation, contract validation,
    and Phase 2 acceptance audit pass.
12. No acceptance result is represented as predictive or trading edge.

Production efficacy remains a later evidence milestone. Phase 2 completion
means trustworthy measurement, not favorable performance.
