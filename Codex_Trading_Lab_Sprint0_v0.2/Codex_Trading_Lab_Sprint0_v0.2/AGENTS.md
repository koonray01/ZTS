# Codex Operating Rules

1. Treat this repository as standalone. Do not inspect, modify, import, mount, or depend on the existing TradingOS main repository.
2. Read the active task pack, architecture, ownership map, schemas, acceptance criteria, and test policy before editing code.
3. Use only public control-plane interfaces. Internal detector invocation order is not chosen ad hoc by Codex.
4. Never create silent mocks, fake runtime evidence, or synthetic results labeled as live.
5. Raw evidence is append-only. Derived outputs never overwrite raw inputs.
6. Every live analysis artifact must carry `run_id`, `snapshot_id`, schema version, component versions, capture time, broker time, and evidence references.
7. Sensors report facts, features, detected events, unknowns, and errors. They never issue BUY/SELL authorization.
8. Scenario ranking is qualitative until calibration evidence exists. Do not invent percentages.
9. Entry engines may create candidates but cannot authorize execution. `permission_state` remains `NOT_EVALUATED` until the separate permission review.
10. Codex may orchestrate workflows and write plans/reports but may not alter deterministic results, raw evidence, or provenance.
11. Unknown, stale, incomplete, mixed-time, or quarantined data stays visible and cannot be converted to neutral.
12. Live order placement, modification, cancellation, and auto-execution are forbidden in MVP code.
13. Every implementation task must produce tests, a run report, a known-gaps report, and files-changed summary.
14. Do not weaken or delete tests to obtain a pass.
15. Any future connection to another system requires an explicit, separately versioned, read-only adapter task approved by the human project owner.
