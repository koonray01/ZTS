# Pending Limit Plan Monitor

A manual pending-limit plan may be registered with:
- plan_id
- candidate_id
- entry range
- invalidation
- expires_at
- linked decision hash

Monitor states:
- ACTIVE
- WINDOW_OPEN
- FILLED_OBSERVED
- CANCEL_RECOMMENDED
- INVALIDATED
- EXPIRED

Runtime only recommends cancellation; it never cancels an order.
