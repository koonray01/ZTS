# Integration Handoff after Sprint 1

## Merge prerequisites
1. Sprint 1 real snapshot contract remains compatible with schema `0.2.0`
2. 20 real MT5 snapshots pass
3. No mixed-time or open-bar leakage
4. Sensor output contract remains locked
5. Human review approves definitions v0.1

## Recommended integration
Copy:
- `src/ctl_eyes/` → project perception package
- `tests/` sensor tests → project tests/perception
- `tools/run_eyes.py` → diagnostic tool only

Then add one adapter:
```python
snapshot = snapshot_service.get(...)
envelope = run_basic_eyes(snapshot)
```

Do not let each sensor call MT5 separately.
