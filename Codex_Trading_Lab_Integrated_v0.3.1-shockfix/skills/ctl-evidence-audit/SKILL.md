# ctl-evidence-audit

        ## Purpose
        Inspect evidence references and unresolved claims.

        ## Allowed tools
        - inspect_evidence_refs
- get_current_state

        ## Required output
        Known evidence, unresolved refs and audit findings.

        ## Prohibited
        - Do not modify raw evidence.
        - Do not change deterministic outputs.
        - Do not place, modify, cancel or close orders.
        - Do not grant permission outside `run_part3`.
        - Do not change policies or skill versions.
