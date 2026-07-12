# System Boundary

## Independence contract
This project is parallel to and independent from the existing TradingOS main system.

It must not share:
- repository
- runtime process
- state machine
- database
- evidence store
- policy files
- locks
- skill registry
- version history
- deployment pipeline

## Future integration rule
Any future connection requires:
1. a separately versioned adapter,
2. read-only by default,
3. explicit source/target schemas,
4. no cross-write capability,
5. independent failure containment,
6. human approval before activation.

## Current integration status
NONE.
