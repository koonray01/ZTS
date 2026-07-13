# Structured Limit Eligibility v0.1

Results:
- LIMIT_READY
- LIMIT_WATCH
- CONFIRMATION_REQUIRED
- LIMIT_REJECTED
- LIMIT_INVALIDATED
- LIMIT_EXPIRED

`LIMIT_READY` means:
- zone is active and structurally traceable
- freshness is acceptable
- RR passes the research threshold
- no blocking shock/conflict
- invalidation is explicit

It does **not** mean:
- trade approved
- order should be placed automatically
- the zone has validated expectancy
