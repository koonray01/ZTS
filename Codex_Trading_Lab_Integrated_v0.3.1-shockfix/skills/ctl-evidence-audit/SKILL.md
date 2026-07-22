---
name: ctl-evidence-audit
description: Use when the user asks for historical analysis performance, Registry integrity, evidence coverage, prediction scoring, or audit findings.
---

# Evidence Audit

This is the primary route for historical performance and Registry audits. A request for current/live analysis instead belongs to `ctl-market-analysis-registry`.

## Inspect

- Immutable decision/event IDs and snapshot bindings
- Evidence references, source class, retrieval time, and hashes
- Scheduled/evaluated jobs, horizons, outcomes, unresolved reasons, and operation logs
- Canonical Registry configuration and continuity across sessions/worktrees

## Output

Separate capability, evidence coverage, scoring coverage, and measured performance. Use `PHASE2_ENABLED_NO_EVENTS` when capability exists without outcome events and `INSUFFICIENT_EVIDENCE` when efficacy cannot be judged. Report gaps and conflicts without converting them into wins or losses.

## Boundaries

Audit read-only. Do not rewrite evidence or journals, reconstruct missing predictions after outcomes, silently select a competing Registry root, claim efficacy from architecture acceptance, grant permission, or write to MT5.
