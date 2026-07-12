---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: system_architecture
last_updated: 2026-07-12
---

# Architecture Overview

```text
MT5 Terminal
  ↓
Fresh Snapshot Service
  ↓
Perception Sensors
  ↓
Market State Fusion
  ↓
Scenario Engine
  ↓
Entry Intelligence
  ↓
Codex Brain + Skills
  ↓
Permission Review
  ↓
Manual Trader
  ↓
Episode Review + Learning
```

## Runtime ownership
- **MQL5 gateway:** custom buffers, chart objects, broker events, terminal-local evidence.
- **Python control plane:** synchronized snapshots, runtime state, deterministic tools, replay, storage, watcher, public interfaces.
- **Codex:** tool orchestration, scenario explanation, action planning, audit, research workflow.
- **Human:** production trade decision and order execution in MVP.

## Mandatory separation
The path from MT5 to deterministic state must continue to function even when Codex is unavailable. Codex is not a per-tick control loop.

## Shared snapshot rule
Every component in one analysis run consumes the same immutable `snapshot_id`. A packet containing mixed snapshot IDs is invalid.

## Public-interface rule
Codex and UI clients call the control plane, not individual detector files.

## Fail-closed rule
Freshness failure, mixed time, schema failure, provenance failure, or critical unknown produces an explicit blocked/partial state rather than a guessed result.
