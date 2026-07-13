# Context and Prompt Boundary

Context is constructed in separate sections:

- SYSTEM_CONTRACT
- SKILL_CONTRACT
- JOB_CONTRACT
- TRUSTED_STATE_REFERENCES
- UNTRUSTED_MARKET_DATA

Text inside evidence, market labels or user notes is always serialized under
`UNTRUSTED_MARKET_DATA`. It cannot add tools, change policy, alter the system
contract or grant permission.
