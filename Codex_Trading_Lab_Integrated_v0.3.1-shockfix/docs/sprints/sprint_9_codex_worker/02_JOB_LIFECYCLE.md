# Job Lifecycle v0.1

```text
QUEUED
→ LEASED
→ RUNNING
→ SUCCEEDED

RUNNING
→ RETRY_WAIT
→ LEASED

RUNNING
→ DEAD_LETTER

QUEUED / RETRY_WAIT
→ CANCELLED
```

Lease expiry returns an unfinished job to `RETRY_WAIT`. Completed jobs are never
claimed again. Every transition is append-only.
