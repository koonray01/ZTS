# Approval and Expiry

Every APPROVED decision binds:
- decision_id
- decision_hash
- snapshot_id
- candidate_id
- account_context_id
- policy_version
- issued_at
- expires_at
- execution_scope = MANUAL_ONLY

A newer snapshot does not inherit approval automatically.
Expired approval requires Part 3 to run again.
