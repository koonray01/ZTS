# Codex Trading Lab — Bootstrap v0.1

Working codename for a standalone agentic trading research and decision system.

## Core objective
Build a Codex-controlled system that reads fresh MT5 data through small deterministic tools, constructs market scenarios, produces sharp but sufficiently frequent entry candidates, supports replay training, and keeps execution manual during the MVP.

## Hard boundary
This repository is independent from the existing TradingOS main system. It does not share runtime state, policies, locks, data stores, repositories, or version history. Any future integration must use an explicit, read-only adapter.

## First delivery target
XAUUSD live vertical slice:

MT5 snapshot → candle/swing/structure → zones + sweep/break/reclaim → market packet → three scenarios → limit/confirmation candidates → Codex action plan → validation report.
