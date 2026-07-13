# Failure and Retry Policy

Retryable:
- provider timeout
- temporary provider unavailable
- lease interruption
- temporary state resolver unavailable

Non-retryable:
- disallowed tool
- skill version mismatch
- invalid job schema
- invalid final result schema
- fabricated permission
- tool budget exceeded
- dependency mismatch

Non-retryable failures go to dead-letter with an audit record.
