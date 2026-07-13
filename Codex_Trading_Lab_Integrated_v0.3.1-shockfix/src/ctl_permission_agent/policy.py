from __future__ import annotations

DEFAULT_RISK_POLICY = {
    "policy_version": "PART3_POLICY_0.1.0",
    "minimum_rr": 1.5,
    "maximum_risk_percent": 1.0,
    "maximum_daily_loss_percent": 3.0,
    "maximum_open_positions": 2,
    "approval_ttl_seconds": 90,
    "allow_structured_limit": True,
    "manual_execution_only": True,
}

REQUIRED_DEPENDENCIES = {
    "snapshot_schema": "0.3.0",
    "market_packet_schema": "0.2.0",
    "scenario_schema": "0.2.0",
    "entry_schema": "0.2.0",
    "decision_core": "0.1.0",
    "part3_policy": "PART3_POLICY_0.1.0",
}
