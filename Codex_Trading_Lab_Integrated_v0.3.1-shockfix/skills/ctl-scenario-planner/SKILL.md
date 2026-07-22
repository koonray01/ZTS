---
name: ctl-scenario-planner
description: Use when the primary market-analysis workflow needs measurable primary and alternative scenarios or a conditional watch setup from validated evidence.
---

# Scenario Planner

For current/live requests, work inside `ctl-market-analysis-registry` using its snapshot and Registry decision; never restart the flow.

## Inputs

- Snapshot-bound market read and deterministic blockers
- User horizon: Scalping, Daytrade, or stated alternative

## Output

Give a primary scenario and bounded alternatives with side, observable activation trigger, invalidation, expiry/horizon, scoring target, and wait conditions. Mark missing measurable fields explicitly.

A Chat-derived plan is `CONDITIONAL_WATCH_SETUP`, never `ZENITH_CANDIDATE`. If trigger, price geometry, stop, one target, horizon, or evidence binding is absent, return `NON_SCORABLE` with reasons and schedule no evaluation job.

## Boundaries

Do not manufacture fields after outcomes, override deterministic blockers, duplicate Registry writes, change evidence or policy, grant permission, or write to MT5.
