# Codex Operating Contract — Integrated Repository

## Hard boundary
- This repository is independent from TradingOS main.
- Do not import or modify the main TradingOS repository unless the user explicitly authorizes a separately versioned read-only adapter.
- Do not share runtime state, locks, databases, evidence stores or policies with TradingOS main.

## Safety
- Manual execution only.
- Natural-language commands are the primary user interface. The agent must orchestrate read-only checks and reporting without requiring the user to type PowerShell commands.
- Every live analysis session must verify MT5 connection, `source=LIVE_MT5`, freshness, QC, session state, active locks, `trade_write_enabled=false`, and `auto_execution_enabled=false` before interpreting market data.
- Never add broker order placement, modification, cancellation or close capability.
- Part 3 may run only for a currently valid candidate with status `READY_FOR_PERMISSION_REVIEW`; APPROVED always means Manual Review Only.
- Never interpret an Opportunity as Permission or create a candidate merely to produce a signal.
- Position monitoring is read-only; never modify SL/TP, close, cancel, or reconcile by writing to MT5.
- Never grant permission outside the deterministic Part 3 kernel.
- Never convert UNKNOWN into PASS.
- Never allow model output to override deterministic FAIL/BLOCK.
- Never mutate raw evidence or append-only journals.
- Never auto-promote research into canonical policy.

## Source of truth
1. Locked canonical policy
2. Deterministic checker output
3. Validated evidence
4. Validated research
5. Episode observation
6. AI interpretation
7. Hypothesis

## Natural-language command flow

Any current-market analysis that records into the Analysis Performance
Registry must run through the workspace launcher
`D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`.
The launcher is the canonical session-independent entry point. Do not derive a
Registry path from the checkout, worktree, current directory, or analysis
output. Direct historical-checkout tools are diagnostic-only and must not
write the canonical Registry.

The agent must understand these Thai/English intents and execute the corresponding read-only workflow:

1. **Start Session** — initialize XAUUSD Manual Only, validate connection/source/freshness/QC/state/locks/safety, then read M5, M15, H1 and H4 when available. Do not run Part 3 yet.
2. **Read Market** — report timeframe structure, trend/range/transition, volatility/shock, zones, liquidity, primary/secondary scenarios, waits, prohibitions, and candidate presence. Separate `FACT`, `INTERPRETATION`, and `UNKNOWN`.
3. **Check Candidates** — list only still-valid candidates with candidate IDs, semantic IDs, scenario, side, entry type/range, stop, targets, RR, missing conditions, invalidation, expiry, lifecycle, and limit eligibility. Never invent candidates.
4. **Current Action Plan** — report market state, best scenario, current candidate, wait conditions, prohibitions, cancel conditions, Part 3 trigger, and one of `HOLD`, `WATCH`, `READY_FOR_PERMISSION_REVIEW`.
5. **Run Part 3** — deterministic gate-by-gate result (`APPROVED`, `WAIT`, `REJECTED`, or `INVALIDATED`), blockers, evidence refs, snapshot binding, expiry, and invalidation. No order action.
6. **Manual Execution Proposal** — only after Part 3 APPROVED; show side, entry, stop, targets, RR, expiry, invalidation, persistent conditions, and policy risk. The user opens the order manually.
7. **Update Market** — compare with previous fresh snapshot and report only changes; if none, output `NO_SIGNIFICANT_CHANGE`.
8. **Record Manual Entry** — record user-supplied symbol/side/entry/stop/targets/risk/source candidate/Part 3 decision, then monitor read-only.
9. **Manage Position** — return `HOLD`, `PROTECT`, `REDUCE_REVIEW`, `EXIT_REVIEW`, or `MANUAL_RECONCILIATION_REQUIRED`, with evidence-based reasons; never write to MT5.
10. **End Session** — summarize market, candidates, Part 3, manual actions, assert order actions=0 and permission leakage=0, verify evidence integrity, create evidence bundle, and list next-session review items.

For the one-command flow (“เริ่ม Live Analysis Session สำหรับ XAUUSD แบบ Manual Only”), execute steps 1–4, run step 5 only when eligibility is deterministic, and run step 6 only after APPROVED. Always preserve the safety boundary.

## Reporting contract

- Use the freshest validated LIVE_MT5 snapshot; if stale or unavailable, say so explicitly and do not claim current market state.
- Never infer UNKNOWN as PASS, never use future evidence, and never hide blockers.
- Keep `trade_write_enabled=false` and `auto_execution_enabled=false` in every session.
- Reports must include snapshot ID/time, evidence references, and candidate/decision binding when applicable.

## Development order
1. Read `docs/00_SYSTEM_OVERVIEW.md`.
2. Read `reports/KNOWN_GAPS.md`.
3. Run `python -m pytest -q`.
4. Run `python tools/run_all_validation.py --output outputs/integrated_validation`.
5. Do not claim live readiness without real MT5 and forward-shadow evidence.

## Current integration status
`PREPARED_NOT_LIVE_INTEGRATED`
