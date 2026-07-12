# Windows MT5 Setup Guide

1. Install MetaTrader 5 terminal and sign in to the intended read-only validation account.
2. Install Python dependencies:

```powershell
python -m pip install -e ".[test]"
python -m pip install MetaTrader5
```

3. Start MT5, open the target symbol in Market Watch, and confirm the symbol name used by the broker, for example `XAUUSD`.
4. Run a read-only probe:

```powershell
python tools/run_mt5_snapshot.py --symbol XAUUSD --run-id RUN-MT5-PROBE --output outputs/mt5_probe
```

5. Run timed forward shadow:

```powershell
python tools/run_forward_shadow.py --symbol XAUUSD --snapshots 120 --interval-seconds 60 --max-snapshot-seconds 300 --output outputs/sprint10_real_forward_shadow_2h
```

The adapter only calls read APIs for terminal identity, account identity, positions, ticks, and closed bars. It does not expose any broker-write method.
