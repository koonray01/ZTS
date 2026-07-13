# CLI Dry Run Report

- Exit code: `0`

```text
{"session_id": "SESSION_XAUUSD_2026_07_12T13_24_52_841230Z", "processed_snapshots": 3, "jobs_queued": 1, "final_state": "STOPPED", "reports": [{"snapshot_id": "SNAP-DIRECTIONAL-MARKET-001", "accepted_events": [], "jobs_created": [], "health": "HEALTHY", "session_state": "ACTIVE"}, {"snapshot_id": "SNAP-DIRECTIONAL-MARKET-002", "accepted_events": [], "jobs_created": [], "health": "HEALTHY", "session_state": "ACTIVE"}, {"snapshot_id": "SNAP-LIVE-SHOCK-003", "accepted_events": ["MARKET_STATE_CHANGED", "SHOCK_DETECTED", "MARKET_STATE_CHANGED", "MARKET_STATE_CHANGED"], "jobs_created": ["JOB_C6283CEC18D2B76637AD"], "health": "HEALTHY", "session_state": "ACTIVE"}], "auto_execution_enabled": false}

Spreadsheet runtime warmup failed during python startup
Traceback (most recent call last):
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/patches/warm_spreadsheet_runtime_on_startup.py", line 26, in warm_spreadsheet_runtime_on_startup
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/spreadsheet_warmup.py", line 785, in warm_spreadsheet_runtime
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/spreadsheet_warmup.py", line 720, in _warm_feature_flows
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/spreadsheet_warmup.py", line 704, in _warm_collaboration_flows
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/generated/interface/models.py", line 30820, in hydrate_crdt_from_proto
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/rpc/remote.py", line 749, in __call__
  File "/tmp/tmp.yTcnQsZYiA/artifact_tool_v2-2.8.4/artifact_tool/rpc/client.py", line 150, in call
artifact_tool.rpc.client.RemoteError: hydrateCrdtFromProto requires an empty collaborative document.
```
