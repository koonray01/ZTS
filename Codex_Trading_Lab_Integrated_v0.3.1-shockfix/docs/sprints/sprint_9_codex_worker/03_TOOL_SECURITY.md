# Tool Security

Effective tools:

```text
Job allowed_tools
∩ Skill manifest allowed_tools
∩ ToolGateway.ALLOWED_TOOLS
```

Additional controls:
- maximum tool calls per job
- duplicate-call loop detection
- strict argument types
- result-size limit
- no permission fabrication
- no raw evidence mutation
- no arbitrary code or shell
