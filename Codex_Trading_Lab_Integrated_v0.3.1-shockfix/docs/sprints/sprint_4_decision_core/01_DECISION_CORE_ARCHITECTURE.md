# Decision Core Architecture

```text
Snapshot
  ↓
Basic Eyes + Advanced Eyes
  ↓
Fusion
  ↓
Compact Market Packet
  ↓
Scenario Engine
  ↓
Entry Engine
  ├─ Structured Limit
  ├─ Early Confirmation
  ├─ Full Confirmation
  └─ Continuation
  ↓
Limit Eligibility Gate
  ↓
Part 3 (outside this pack)
```

Watcher uses packet diffs:

```text
Previous State + Current State
  ↓
Deterministic Diff
  ↓
Significant Event?
  ├─ No: persist only
  └─ Yes: create Codex job later
```
