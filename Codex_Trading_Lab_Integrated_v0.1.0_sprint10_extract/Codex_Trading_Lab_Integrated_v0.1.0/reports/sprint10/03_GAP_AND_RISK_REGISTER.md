# Sprint 10 Gap And Risk Register

| Risk | Status | Handling |
|---|---|---|
| Old absolute `/mnt/data` strings in historical report/example outputs | Open | Non-runtime hygiene gap; not changed in this sprint to avoid unrelated artifact churn |
| Real MT5 session duration | Open | 20 real snapshots were captured rapidly with interval 0; longer timed shadow remains recommended |
| Candidate count in real shadow | Open | Real run produced 60 scenarios and 0 entry candidates; no Part 3 requests occurred |
| Custom indicator/repaint audit | Open | Not implemented in Sprint 10 adapter; snapshot service captures native closed OHLC bars |
| Broker terminal variability | Open | Adapter fails closed on unavailable package, terminal, symbol, tick, or bar data |
| Evidence collision on rerun into same output path | Expected | Append-only store quarantines changed duplicate content |
| Live provider | Not connected | Scripted worker used; no live provider credentials added |

Critical trade-write risk: none found in runtime scan.
