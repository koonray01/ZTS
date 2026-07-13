# Sprint 9 — Codex Worker Integration

## Prerequisites
- Sprint 1–8 contracts pass
- external provider credentials stored outside repository
- provider adapter approved
- redaction and timeout policy approved

## Mission
Connect a real Codex/model provider to the prepared worker boundary.

## Definition of Done
- one worker claims each job exactly once
- lease recovery works
- skill versions match
- tool allowlist intersection enforced
- tool and token budgets enforced
- final result schema passes
- deterministic permission cannot be overridden
- retry/dead-letter classifications pass
- audit and result chains verify
- no trade-write API
- shadow worker session completed
