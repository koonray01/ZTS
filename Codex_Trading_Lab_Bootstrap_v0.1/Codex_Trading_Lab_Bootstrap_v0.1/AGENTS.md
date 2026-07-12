# Codex Operating Rules

1. Treat this repository as standalone. Do not inspect, modify, import, or depend on the existing TradingOS main repository unless a task explicitly authorizes a read-only adapter.
2. Read the task pack, architecture, ownership map, schemas, acceptance criteria, and test policy before editing code.
3. Do not create silent mocks, fake runtime evidence, or synthetic results labeled as live.
4. Raw evidence is append-only. Derived files must never overwrite raw inputs.
5. Sensors report facts, features, and detected events; they never issue BUY/SELL commands.
6. Codex may orchestrate workflows and produce plans but may not alter deterministic checker results.
7. Live order placement is out of scope for MVP. Execution mode is manual.
8. Every implementation task must produce tests, a run report, known gaps, and files-changed summary.
9. Do not relax tests to make a build pass.
10. Unknown, stale, incomplete, or mixed-time data must remain visible and must not be converted to neutral.
