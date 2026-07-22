# Market Analysis Registry Skill Design

## Objective

Make every normal-language current-market analysis, market update, two-way comparison, and setup request use one consistent read-only workflow. The workflow captures fresh evidence, keeps Zenith and external reasoning separately attributable, records measurable decisions in the Analysis Performance Registry, and performs bounded catch-up automatically.

This design changes agent and skill instructions plus the minimum orchestration integration needed to create and persist structured Chat Model envelopes. It does not enable background services, Part 3, permission, or broker writes.

## Selected Architecture

Add one orchestration skill, `ctl-market-analysis-registry`, as the canonical entry point. Existing domain skills retain their narrow responsibilities and delegate orchestration to the new skill. `AGENTS.md` defines the repository-wide invariants and command routing without duplicating the complete workflow.

Responsibilities:

- `AGENTS.md`: mandatory routing, freshness, safety, automatic Registry policy, and failure precedence.
- `ctl-market-analysis-registry`: ordered end-to-end workflow and output contract.
- `ctl-market-read`: deterministic Zenith market interpretation only.
- `ctl-scenario-planner`: scenario construction and measurable prediction fields.
- `ctl-entry-evaluator`: Candidate truth and setup classification.
- `ctl-evidence-audit`: evidence, Registry, and audit verification.
- `update_market_analysis.py`: canonical foreground execution path, structured
  Chat-envelope input, automatic Registry recording, and bounded catch-up.
- `ctl_analysis_registry.chat_model`: validation and freezing of Chat Model
  predictions derived from decision-time evidence.

## Trigger Scope

The orchestration skill applies to Thai or English requests for:

- current/live market analysis;
- market updates or continuation of an earlier plan;
- Zenith plus external analysis or comparison;
- Scalping or Daytrade setup construction;
- a combined analysis and performance-recording request.

Historical audit-only, replay, position-management, and explicit Part 3 requests keep their existing routes.

## Canonical Flow

1. Capture a new read-only MT5 snapshot for any current/live request.
2. Require `source=LIVE_MT5`, `freshness=FRESH`, QC `PASS`, terminal connection, and all zero-write safety invariants.
3. Run deterministic Zenith analysis on the bound snapshot.
4. Run external research only when requested or when the request says “both”; label sources and retrieval times and never substitute external prices for the MT5 quote. External documents are evidence, not a third prediction system.
5. Compare Zenith and external conclusions while preserving attribution. External interpretation cannot override deterministic blockers, Candidate state, Risk, or Permission.
6. Classify setup output as exactly one of:
   - `ZENITH_CANDIDATE`: emitted by the deterministic system;
   - `CONDITIONAL_WATCH_SETUP`: a non-permission Chat plan with explicit trigger, invalidation, expiry/horizon, and targets;
   - `NO_SETUP`: insufficient or blocked evidence.
7. Convert Chat conclusions, including conclusions derived from external
   evidence, into a structured `CHAT_MODEL` envelope before the response is
   finalized. Preserve source URLs, retrieval times, content hashes, and claim
   evidence bindings. Never treat quoted or summarized source text itself as a
   model prediction.
8. Freeze and record Zenith and Chat views automatically. Only a contract with measurable machine-readable fields becomes scorable and receives evaluation jobs.
9. Run bounded catch-up automatically in the same foreground request. This is not a persistent background process.
10. Report market evidence, both analyses when applicable, comparison, setup class, Registry result, catch-up result, and safety counters.

## Canonical Runtime Storage

Live analysis uses one durable Registry root relative to the selected canonical
runtime checkout:

`outputs/analysis_registry/`

It contains the ledger, SQLite projection, follow-up evidence, operation log,
and writer lease. Changing the per-analysis output directory must not change
the Registry root. Replay and tests must use explicitly separate paths and
retain their source class; they cannot write into the live Registry.

The operator response must show the resolved Registry root. If multiple Git
worktrees exist, the workflow must not silently create independent live
histories. The canonical runtime checkout/path must be selected explicitly or
reported as `REGISTRY_PATH_AMBIGUOUS`.

## Registry Contract

Automatic recording is the default and does not require the user to say “record Registry.” The response must expose:

- `registry_recording_status`;
- immutable decision/event IDs;
- scheduled-job count;
- catch-up status, processed count, and remaining count;
- why a decision was non-scorable when no job was created.

The workflow must never manufacture horizons, price geometry, or evaluation criteria from prose after the outcome is known. Registry failure is visible and does not silently downgrade to an unrecorded “successful” analysis.

### Scorable Conditional Setup

A `CONDITIONAL_WATCH_SETUP` becomes scorable only when frozen before its
outcome and includes:

- side and machine-readable activation trigger;
- entry geometry and side-aware price semantics;
- stop and exactly one scoring target;
- expiry and evaluation horizon;
- invalidation rule;
- snapshot and decision-time evidence binding.

Additional targets are excursion milestones and do not create additional
headline predictions. Missing fields produce `NON_SCORABLE` with explicit
reason codes and zero scheduled jobs.

## Failure and Safety Precedence

- No fresh MT5 evidence: current price and live Zenith analysis are unavailable.
- QC or connection failure: stop before market interpretation and recording of scorable live decisions.
- External provider unavailable: Zenith may complete, but the external view and comparison remain `NEEDS_DATA`.
- Registry recording failure: return the analysis with `REGISTRY_BLOCKED` and explicit diagnostics; do not claim audit continuity.
- Catch-up failure: preserve the newly recorded decision when valid, report `CATCHUP_BLOCKED`, and leave pending jobs intact.
- Ambiguous or multiple live Registry roots: report
  `REGISTRY_PATH_AMBIGUOUS` and do not split audit history silently.
- Any trade-write, automatic-execution, order-action, or permission-leakage value above zero blocks the response as a safety violation.

Part 3 remains explicit and separate. A Candidate, conditional setup, comparison, or Registry record never grants permission.

## Independent Status Gates

The workflow reports these independently:

- `analysis_status`;
- `external_evidence_status`;
- `registry_recording_status`;
- `catchup_status`;
- `safety_status`.

For example, a valid Zenith read with a Registry write failure is
`ANALYSIS_COMPLETE` plus `REGISTRY_BLOCKED`; it is not an end-to-end success
and cannot claim continuous audit coverage.

## Output Shape

Every applicable response uses this order:

1. evidence and current quote;
2. Zenith view;
3. external view, when requested;
4. comparison;
5. setup classification and conditions;
6. current action (`HOLD`, `WATCH`, or `READY_FOR_PERMISSION_REVIEW`);
7. Registry/catch-up status;
8. safety assertion.

The output distinguishes runtime facts, sourced external facts, interpretation, and unknowns.

## Verification Strategy

Skill pressure scenarios verify that an agent:

- does not reuse a prior “fresh” snapshot for a new current request;
- automatically records without an explicit Registry phrase;
- does not label a Chat conditional setup as a Zenith Candidate;
- does not invent a scorable job when trigger, invalidation, horizon, or criteria are missing;
- reports external-provider and Registry failures explicitly;
- runs bounded catch-up without claiming a background daemon;
- preserves zero broker writes and Permission separation.

Repository validation checks frontmatter, required sections, cross-references, command routing, and prohibited claims. Existing full tests and contract validation must remain green.

All touched repository skills receive valid YAML frontmatter, UTF-8 text,
trigger-focused descriptions, and non-duplicated responsibility boundaries.
Tests cover automatic routing, structured Chat-envelope validation, canonical
Registry-path resolution, independent status gates, and non-scorable reason
codes.

## Non-Goals

- No persistent automatic worker.
- No broker order placement or modification.
- No automatic Part 3 call.
- No promotion or trading-edge claim from architecture acceptance.
- No changes to deterministic price, scenario, Candidate, Risk, or Permission policies.
