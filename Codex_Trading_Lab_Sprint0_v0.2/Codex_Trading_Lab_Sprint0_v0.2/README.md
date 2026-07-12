# Codex Trading Lab — Sprint 0 Contract v0.2

Standalone agentic trading research and decision platform.

## Core objective
Use synchronized fresh MT5 evidence, deterministic perception tools, scenario planning, and Codex orchestration to produce sharp entry plans without reducing opportunity throughput unnecessarily.

## Hard boundary
This repository is independent from the existing TradingOS main system. It shares no repository, runtime, state, database, evidence store, policy, lock, skill registry, version history, or deployment pipeline.

## Current status
Sprint 0 architecture and interface contract is complete. Sprint 1 may implement the fresh MT5 snapshot vertical slice only. Live order placement remains forbidden.

## Contract validation

```bash
python tools/validate_contracts.py
python -m unittest discover -s tests -v
```
