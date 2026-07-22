# Market Skill Pressure Baseline - 2026-07-22

This is a documentation-routing evaluation. It is not a market prediction,
performance result, or trading-edge claim. Fresh-context agents read only the
current `AGENTS.md`, `skills.md`, and existing domain skills; they did not read
the proposed design or plan.

| Intent | Expected primary route | Observed baseline gap |
|---|---|---|
| current XAUUSD analysis | `ctl-market-analysis-registry` | selected `ctl-market-read`; current-vs-session-start routing was ambiguous |
| Zenith plus external analysis | `ctl-market-analysis-registry` | selected `ctl-market-read`; no Chat integration or failure status was defined |
| historical performance audit | `ctl-evidence-audit` | no route covered retrospective Registry performance |
| analysis from another worktree | `ctl-market-analysis-registry` | launcher was canonical, but config resolution and catch-up behavior were undocumented |
| unavailable Chat registration | `ctl-market-analysis-registry` | no `CHAT_REGISTRATION_BLOCKED` status existed |
| Registry write failure | `ctl-market-analysis-registry` | no prescribed independent Registry failure status or recovery contract existed |
| explicit Part 3 | `ctl-part3-preexecute` | route was correct, with a minor naming mismatch against `run_part3_manual_review` |

## Baseline failure patterns

- No single skill owned the end-to-end current-market workflow.
- Domain skills had no trigger metadata or explicit delegation boundary.
- External analysis, structured Chat registration, and evidence provenance were
  unsupported or ambiguous in the instruction surface.
- Foreground bounded catch-up and canonical-config failure behavior were absent.
- Analysis success and Registry/audit-continuity failure had no independent
  status contract.
- Safety and Part 3 eligibility were already conservative and must be retained.

## Post-update validation

Not run yet. The same seven intents will be repeated after the new skill and
routing contracts are installed.
