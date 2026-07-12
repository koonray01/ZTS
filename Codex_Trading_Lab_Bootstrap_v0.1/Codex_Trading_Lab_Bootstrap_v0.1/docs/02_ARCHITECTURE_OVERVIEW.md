# Architecture Overview

```text
MT5
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
- MQL5: custom indicator buffers, chart objects, broker events
- Python: runtime, state, deterministic tools, replay, storage, watcher
- Codex: orchestration, scenario explanation, action planning, research workflow
- Human: final trade decision and order execution during MVP
