---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: system_architecture
last_updated: 2026-07-12
---

# Repository Structure

```text
Codex_Trading_Lab/
├── AGENTS.md
├── README.md
├── config/
├── docs/
├── tasks/
├── schemas/
├── examples/
│   ├── valid/
│   └── invalid/
├── src/
│   ├── control_plane/
│   ├── mt5_gateway/
│   ├── perception/
│   ├── scenario/
│   ├── entry/
│   ├── watcher/
│   ├── training/
│   ├── knowledge/
│   └── safety/
├── skills/
├── data/
│   ├── evidence/
│   │   ├── raw/
│   │   ├── normalized/
│   │   └── quarantine/
│   ├── manifests/
│   └── state/
├── outputs/
├── reports/
├── tools/
└── tests/
```

## Runtime path rule
The repository root is supplied by `CODEX_TRADING_LAB_ROOT`. Production code must not embed user-specific absolute paths.

## Data path rule
Raw and normalized data are separate. Raw files are immutable; normalized and output files reference raw content hashes.
