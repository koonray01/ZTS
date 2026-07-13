# Tool Gateway Policy v0.1

Allowlisted tools:
- get_current_state
- list_entry_candidates
- run_part3
- explain_decision
- build_manual_execution_proposal
- inspect_evidence_refs
- build_codex_job

Prohibited:
- arbitrary shell
- arbitrary file write
- order_send / trade request
- policy mutation
- raw evidence mutation
- checker-result mutation
- unrestricted Python execution

Tool calls and outputs must validate against schemas and be journaled.
