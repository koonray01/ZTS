# Case Partitions

Supported partitions:

- DEV
- VALIDATION
- LOCKED_OOS
- FORWARD_SHADOW

Rules:
- DEV may be used for detector development.
- VALIDATION may compare frozen versions.
- LOCKED_OOS must not be used for tuning.
- FORWARD_SHADOW uses production-like runtime with no execution.
