# Worker Result Contract

Final result separates:

- FACTS
- INTERPRETATIONS
- UNKNOWNS
- NEXT ACTION
- PERMISSION CLAIM
- TOOL TRACE
- TOKEN USAGE

Rules:
- FACTS require evidence references.
- Interpretation cannot be presented as deterministic fact.
- Permission defaults to NOT_EVALUATED.
- APPROVED requires a successful `run_part3` tool result in the same job.
- Result contains no order command.
