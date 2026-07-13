# Worker Architecture

```text
Watcher
  ↓
Codex Job Packet
  ↓
Worker Job Store
  ↓
Lease Owner
  ↓
Skill Loader
  ↓
Context Builder
  ↓
Provider Adapter
  ↔ Allowlisted Tool Session
  ↓
Structured Worker Result
  ↓
Result Store + Audit
```

Deterministic state and tools remain outside the model. The worker coordinates;
it does not become the source of market truth.
