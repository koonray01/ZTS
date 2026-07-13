# Position Management Policy v0.1

Runtime reads observed positions and produces recommendations:

- HOLD
- PROTECT
- REDUCE_REVIEW
- EXIT_REVIEW
- MANUAL_RECONCILIATION_REQUIRED

It does not modify SL/TP or close orders.

Position review separates:
- entry origin
- scenario integrity
- structure degradation
- shock state
- progress in R
- protection state
- manual action recommendation
