# Codex Skill Model v0.1

Skills are workflow instructions, not sources of market truth.

Initial skills:
- ctl-market-read
- ctl-scenario-planner
- ctl-entry-evaluator
- ctl-part3-preexecute
- ctl-evidence-audit
- ctl-live-event-review

Every skill declares:
- skill_id and version
- allowed tools
- input/output contracts
- policy dependencies
- prohibited actions

Dependency mismatch blocks the skill.
