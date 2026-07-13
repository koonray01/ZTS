# Knowledge Architecture

```text
Evidence Store
  ↓
Episode Memory
  ↓
Research Knowledge
  ↓
Canonical Knowledge
  ↓
Skill Update Proposal
```

## Stores
- `data/evidence/` — references and manifests
- `data/episodes/` — replay/live-shadow/live-execution records
- `data/research/` — hypotheses, experiments and findings
- `data/canonical/` — approved locked policies
- `data/proposals/` — change and skill-update proposals

Each store is append-only or new-version-only.
