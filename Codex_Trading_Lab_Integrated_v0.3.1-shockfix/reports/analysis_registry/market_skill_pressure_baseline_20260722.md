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

Fresh-context agents repeated all seven intents using only the updated
`AGENTS.md`, `skills.md`, and relevant skills. No agent edited files or read
the design, plan, or this report.

| Intent | Selected route | Fresh snapshot | Registry / failure behavior | Part 3 | Safety |
|---|---|---|---|---|---|
| current XAUUSD analysis | `ctl-market-analysis-registry` | required | automatic canonical recording; `REGISTRY_BLOCKED` remains independent | not automatic | foreground, zero broker writes |
| Zenith plus external analysis | `ctl-market-analysis-registry` | required | separate attribution; `CHAT_REGISTRATION_BLOCKED` or `EXTERNAL_EVIDENCE_PARTIAL` is visible | not automatic | foreground, zero broker writes |
| historical performance audit | `ctl-evidence-audit` | not required | read-only canonical audit; capability, coverage, and efficacy are separate | not allowed by audit intent | no broker writes |
| analysis from another worktree | `ctl-market-analysis-registry` | required | same workspace launcher/root; no local fallback | not automatic | bounded foreground catch-up |
| unavailable Chat registration | `ctl-market-analysis-registry` | required | Chat prediction is not falsely registered; base statuses remain independent | Chat setup cannot promote eligibility | zero broker writes |
| Registry write failure | `ctl-market-analysis-registry` | required | analysis may complete but registration reports `REGISTRY_BLOCKED`; no audit-continuity claim | not automatic | no fallback or daemon |
| explicit Part 3 | `ctl-part3-preexecute` | verify bound freshness | deterministic existing Candidate/evidence review | only when all eligibility gates pass | APPROVED is Manual Review Only |

All expected primary routes matched. Agents consistently required one fresh
snapshot for new current/live work, automatic canonical registration, bounded
foreground catch-up, independent status reporting, explicit Part 3 intent and
eligibility, `order_actions=0`, and `permission_leakage=0`.

### Conservatively unresolved semantics

The instruction layer intentionally does not invent runtime policy for
concurrent-request deduplication, partial transaction recovery, whether a
failed Registry write independently blocks a later Part 3 request, Part 3
result persistence, or deterministic mapping of each failed Part 3 precondition
to WAIT/REJECTED/INVALIDATED. Agents must expose these as blockers or UNKNOWN
and defer to implemented deterministic policy rather than infer behavior.

### Verification evidence

- Agent/Skill plus security contracts: 14 passed.
- Full repository suite: 227 passed.
- Integrated validation: 9 checks, all passed.
- Contract validation: PASS, 39 schemas.
