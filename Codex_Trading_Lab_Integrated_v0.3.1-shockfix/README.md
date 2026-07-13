# Codex Trading Lab — Integrated v0.1.0

Repository รวมของระบบ **Codex Trading Lab** ซึ่งแยกขนานและไม่ใช้ Runtime,
State, Policy, Lock, Evidence Store หรือ Version ร่วมกับ TradingOS ระบบหลัก

## Current pipeline

```text
MT5 Snapshot Contract
→ Basic Eyes
→ Advanced Eyes
→ Decision Core
→ Part 3 Permission
→ Live Runtime
→ Replay & Training
→ Knowledge & Learning
→ Codex Worker
```

## Current modules

- `ctl_eyes`
- `ctl_advanced_eyes`
- `ctl_decision_core`
- `ctl_permission_agent`
- `ctl_live_runtime`
- `ctl_replay_training`
- `ctl_knowledge_learning`
- `ctl_codex_worker`

## Important status

- Unified code and contracts: prepared
- Synthetic automated validation: available
- Real MT5 snapshot adapter: not implemented/validated
- Live model-provider adapter: not connected
- Forward shadow validation: not run
- Auto execution: disabled and outside scope
- Trading edge: not validated

## Quick validation

```bash
python -m pytest -q
python tools/run_all_validation.py --output outputs/integrated_validation
```

## Source preservation

Every preparation pack is preserved under `archive/source_packs/`. Generated
caches such as `.pytest_cache`, `__pycache__` and `.pyc` were intentionally excluded.

## Next real milestone

Implement Sprint 1 as a real standalone MT5 Snapshot Service, then run Sprint 10
Forward Shadow Validation without sending any broker order.
