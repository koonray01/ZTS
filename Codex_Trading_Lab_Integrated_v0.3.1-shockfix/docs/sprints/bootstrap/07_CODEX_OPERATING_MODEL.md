# Codex Operating Model

## Codex role
Executive brain and research orchestrator.

## Public tools only
- get_fresh_snapshot
- analyze_market
- get_scenarios
- get_entry_candidates
- run_limit_gate
- run_permission_review
- inspect_evidence
- review_position
- close_episode

## Codex must not call internal detector files directly
The control plane owns detector order and dependency rules.

## Skill families
- market-intake
- market-read
- structure-audit
- scenario-planner
- entry-evaluator
- limit-evaluator
- permission-review
- position-monitor
- evidence-audit
- replay-training
- learning-orchestrator
