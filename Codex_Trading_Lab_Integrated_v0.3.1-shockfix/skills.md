# Natural-Language Skill Index

Choose one primary route; users should not need to type shell commands.

| Intent | Primary skill |
|---|---|
| Current/live market, update, Zenith + external/both, Scalping, Daytrade | `ctl-market-analysis-registry` |
| Historical performance or Registry evidence audit | `ctl-evidence-audit` |
| Position monitoring or live-event review | `ctl-live-event-review` |
| Explicit deterministic Part 3 review | `ctl-part3-preexecute` |

Supporting skills are invoked by the primary route without restarting it:

- `ctl-market-read`: snapshot-bound Zenith market interpretation.
- `ctl-scenario-planner`: measurable scenarios and conditional plans.
- `ctl-entry-evaluator`: Candidate truth and setup classification.

All applicable current analysis uses the canonical workspace launcher and Registry root defined in `AGENTS.md`, records automatically, runs bounded catch-up in the foreground, and preserves Manual Only/no-broker-write safety.
