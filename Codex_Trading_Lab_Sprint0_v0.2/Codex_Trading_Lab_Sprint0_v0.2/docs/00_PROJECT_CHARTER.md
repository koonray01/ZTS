---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: human_project_owner
last_updated: 2026-07-12
---

# Project Charter

## Mission
Create a standalone agentic trading research and decision platform whose purpose is practical, sharp, timely entry planning with enough opportunity throughput to remain useful.

## System formula
Fresh Evidence → Perception → Market State → Scenario Tree → Entry Candidates → Permission Review → Manual Execution → Review → Learning

## Primary optimization objective
Optimize **entry decision quality and usable opportunity throughput together**.

The system must not maximize selectivity alone. A filter is valuable only when evidence shows that it removes more poor opportunities than good ones, or materially improves risk-adjusted outcomes without unacceptable entry delay.

## Success definition
The system should:
- reduce avoidable bad entries,
- detect usable opportunities early enough,
- preserve multiple entry styles where justified,
- expose uncertainty and conflicts,
- make every conclusion auditable,
- measure blocked winners, blocked losers, missed valid setups, entry latency, and candidate frequency.

## MVP scope
- Symbol: XAUUSD
- Timeframes: M5, M15, H1; H4 optional context
- Data source: local MT5 terminal
- Execution: manual only
- First delivery: fresh synchronized snapshot contract

## Non-goals
- automatic order execution,
- self-modifying production rules,
- full ICT/SMC coverage before primitives,
- multi-symbol production,
- cloud deployment,
- fabricated probabilities,
- integration with the existing TradingOS main system.
