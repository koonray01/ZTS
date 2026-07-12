---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: system_architecture
last_updated: 2026-07-12
---

# System Boundary

## Independence contract
Codex Trading Lab is a parallel, isolated project.

It must not share with any existing TradingOS system:
- repository or Git history,
- runtime process or job queue,
- state machine or state files,
- database or evidence store,
- policies, locks, permission decisions, or risk state,
- skills or skill registry,
- versions, deployment pipeline, or secrets.

## Forbidden dependency classes
- source-code imports,
- file-system reads from the other repository,
- database connections,
- environment-variable reuse whose value grants cross-system access,
- shared mutable folders,
- cross-write adapters,
- automatic migration of policies or lessons.

## Future integration rule
A future connection is allowed only through a separately approved adapter that is:
1. separately versioned,
2. read-only by default,
3. schema-bound,
4. fail-closed,
5. independently testable,
6. unable to write to either source system,
7. activated explicitly by a human.

## Current integration status
`NONE`

## Boundary verification
Sprint tests must scan project source and configuration for forbidden imports, absolute paths, shared database references, and cross-write capabilities.
