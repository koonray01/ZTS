# Known Gaps

1. No real standalone MT5 Snapshot Service exists yet.
2. Broker timestamp, spread, tick and closed-bar integrity are unverified.
3. Custom indicator buffer mapping and repaint/future-leakage audits are incomplete.
4. No live model-provider adapter or credential boundary has been tested.
5. No end-to-end forward shadow session has been run.
6. Position monitoring is fixture-based and does not read a real account.
7. Replay cases are synthetic and do not establish trading edge.
8. Promotion thresholds are governance scaffolding, not statistical proof.
9. No broker order capability exists; this is intentional.
10. The repository is not approved for execution scale-up.
