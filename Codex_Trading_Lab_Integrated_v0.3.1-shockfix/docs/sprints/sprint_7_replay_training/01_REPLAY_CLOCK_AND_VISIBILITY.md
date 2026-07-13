# Replay Clock and Visibility

Replay time is the maximum information time visible to the trainee.

A visible snapshot must satisfy:

```text
bar.close_time <= replay_time
evidence.first_available_at <= replay_time
boundary.first_seen_at <= replay_time
```

Data after replay time remains under `hidden/` and is unavailable through the
normal ReplaySession API.

Any future reference submitted by the trainee creates:
`FUTURE_LEAKAGE_VIOLATION`.
