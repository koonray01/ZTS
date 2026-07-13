# Test Summary

| Command | Result |
|---|---|
| `python -m pytest -q` | 44 passed |
| `python tools/run_all_validation.py --output outputs/sprint11_validation_after_session2_20260713_124712` | 9 checks passed |
| `python tools/validate_contracts.py` | 25 schemas passed |
| `rg -n "...trade-write tokens..." src tools` | no matches |
| freshness-fix canary 10 snapshots | TIMED_CANARY_PASS |
| session 2 timed shadow 120 snapshots | TIMED_FORWARD_SHADOW_PASS |

Evidence bundles are separate from this release.
