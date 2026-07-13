# Session State Machine v0.1

```text
CREATED
  → STARTING
  → ACTIVE
  → PAUSED
  → ACTIVE
  → LOCKED
  → ACTIVE (manual unlock only)
  → STOPPED
```

## Semantics
- ACTIVE: new Part 3 requests allowed
- PAUSED: no new entries; monitoring continues
- LOCKED: no new entries; critical health condition or manual lock
- STOPPED: no new processing

Invalid transitions are rejected and journaled.
