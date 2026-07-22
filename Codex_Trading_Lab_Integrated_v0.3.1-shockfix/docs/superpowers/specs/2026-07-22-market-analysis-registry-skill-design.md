# Market Analysis Registry Skill Design

## Objective

Make every normal-language current-market analysis, market update, two-way comparison, and setup request use one consistent read-only workflow. The workflow captures fresh evidence, keeps Zenith and external reasoning separately attributable, records measurable decisions in the Analysis Performance Registry, and performs bounded catch-up automatically.

This design changes agent and skill instructions only. It does not enable background services, Part 3, permission, or broker writes.

## Selected Architecture

Add one orchestration skill, `ctl-market-analysis-registry`, as the canonical entry point. Existing domain skills retain their narrow responsibilities and delegate orchestration to the new skill. `AGENTS.md` defines the repository-wide invariants and command routing without duplicating the complete workflow.

Responsibilities:

- `AGENTS.md`: mandatory routing, freshness, safety, automatic Registry policy, and failure precedence.
- `ctl-market-analysis-registry`: ordered end-to-end workflow and output contract.
- `ctl-market-read`: deterministic Zenith market interpretation only.
- `ctl-scenario-planner`: scenario construction and measurable prediction fields.
- `ctl-entry-evaluator`: Candidate truth and setup classification.
- `ctl-evidence-audit`: evidence, Registry, and audit verification.

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
4. Run external research only when requested or when the request says “both”; label sources and retrieval times and never substitute external prices for the MT5 quote.
5. Compare Zenith and external conclusions while preserving attribution. External interpretation cannot override deterministic blockers, Candidate state, Risk, or Permission.
6. Classify setup output as exactly one of:
   - `ZENITH_CANDIDATE`: emitted by the deterministic system;
   - `CONDITIONAL_WATCH_SETUP`: a non-permission Chat plan with explicit trigger, invalidation, expiry/horizon, and targets;
   - `NO_SETUP`: insufficient or blocked evidence.
7. Freeze and record Zenith and Chat views automatically. Only a contract with measurable machine-readable fields becomes scorable and receives evaluation jobs.
8. Run bounded catch-up automatically in the same foreground request. This is not a persistent background process.
9. Report market evidence, both analyses when applicable, comparison, setup class, Registry result, catch-up result, and safety counters.

## Registry Contract

Automatic recording is the default and does not require the user to say “record Registry.” The response must expose:

- `registry_recording_status`;
- immutable decision/event IDs;
- scheduled-job count;
- catch-up status, processed count, and remaining count;
- why a decision was non-scorable when no job was created.

The workflow must never manufacture horizons, price geometry, or evaluation criteria from prose after the outcome is known. Registry failure is visible and does not silently downgrade to an unrecorded “successful” analysis.

## Failure and Safety Precedence

- No fresh MT5 evidence: current price and live Zenith analysis are unavailable.
- QC or connection failure: stop before market interpretation and recording of scorable live decisions.
- External provider unavailable: Zenith may complete, but the external view and comparison remain `NEEDS_DATA`.
- Registry recording failure: return the analysis with `REGISTRY_BLOCKED` and explicit diagnostics; do not claim audit continuity.
- Catch-up failure: preserve the newly recorded decision when valid, report `CATCHUP_BLOCKED`, and leave pending jobs intact.
- Any trade-write, automatic-execution, order-action, or permission-leakage value above zero blocks the response as a safety violation.

Part 3 remains explicit and separate. A Candidate, conditional setup, comparison, or Registry record never grants permission.

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

## Non-Goals

- No persistent automatic worker.
- No broker order placement or modification.
- No automatic Part 3 call.
- No promotion or trading-edge claim from architecture acceptance.
- No changes to deterministic price, scenario, Candidate, Risk, or Permission policies.
