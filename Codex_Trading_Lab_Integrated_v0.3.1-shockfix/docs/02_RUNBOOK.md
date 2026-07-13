# Local Runbook

## Install
```bash
python -m pip install -e ".[test]"
```

## Automated tests
```bash
python -m pytest -q
```

## Integrated CLI validation
```bash
python tools/run_all_validation.py --output outputs/integrated_validation
```

## Individual entry points
- `run_eyes.py`
- `run_advanced_eyes.py`
- `run_decision_core.py`
- `run_permission_agent.py`
- `run_live_session.py`
- `run_replay_case.py`
- `run_learning_cycle.py`
- `run_worker_dry_run.py`

All current runs use fixtures. They do not connect to MT5 or a live model provider.
