# Sprint 10 Baseline Verification

Decision: `CONDITIONAL_PASS`

## Environment

- OS: Windows 11 `10.0.26200`
- Python: `3.14.3`
- `jsonschema`: `4.26.0`
- `pytest`: `9.0.2`
- `MetaTrader5`: `5.0.5640`

## Baseline Commands

| Check | Command | Result |
|---|---|---|
| ZIP hash | `Get-FileHash -Algorithm SHA256 Codex_Trading_Lab_Integrated_v0.1.0.zip` | PASS |
| PACK_MANIFEST integrity | inline Python manifest verifier | PASS: 1470 entries, 0 missing, 0 duplicate, 0 hash mismatch |
| Python compile | `python -m compileall -q src tools tests` | PASS |
| Schema validation | `python tools/validate_contracts.py` | PASS: 25 schemas |
| Unit tests | `python -m pytest -q` | PASS: 33 passed before Sprint 10 changes |
| Integrated CLI | `python tools/run_all_validation.py --output outputs/sprint10_baseline_validation` | PASS: 9 checks |
| Runtime trade-write scan | `rg ... src tools` | PASS |
| Cross-system scan | `rg ... src tools tests config schemas skills docs reports tasks examples` | CONDITIONAL: historical docs/examples mention TradingOS boundary and old `/mnt/data` paths |
| Raw-bar compact-context leakage | inspected worker compact context/tool result | PASS: model-facing compact payload excludes raw bars |
| Permission leakage | inspected schemas/tests/runtime | PASS: permission remains deterministic Part 3/manual-only |

## Timed Runs

- Pytest start: `2026-07-12T14:47:14.3840788Z`
- Pytest end: `2026-07-12T14:47:22.9560247Z`
- Pytest exit: `0`
- Integrated CLI start: `2026-07-12T14:47:14.4672315Z`
- Integrated CLI end: `2026-07-12T14:47:30.8648423Z`
- Integrated CLI exit: `0`

## Conditional Items

- Active historical reports/examples contain old absolute `/mnt/data/...` output strings. They are not runtime dependencies, but remain a baseline hygiene gap.
- Contract validator currently has no active `examples/valid` or `examples/invalid` files, so it validates schemas but not root example fixtures.

No critical trade-write capability was found, so Sprint 10 continued.
