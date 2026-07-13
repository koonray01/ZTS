# Model Provider Handoff

The prepared interface accepts a context envelope and returns one turn:

```text
TOOL_CALLS
or
FINAL
```

A real adapter must add:
- credential isolation
- request timeout
- provider request ID
- usage accounting
- transient/permanent error classification
- redaction policy
- rate-limit handling
- integration tests

This pack includes only `ScriptedProvider`; no network request is made.
