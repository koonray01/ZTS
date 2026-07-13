# ctl-scenario-planner

        ## Purpose
        Explain the rule-based scenario tree and next observable events.

        ## Allowed tools
        - get_current_state
- inspect_evidence_refs

        ## Required output
        Primary, alternatives, invalidation and what to wait for.

        ## Prohibited
        - Do not modify raw evidence.
        - Do not change deterministic outputs.
        - Do not place, modify, cancel or close orders.
        - Do not grant permission outside `run_part3`.
        - Do not change policies or skill versions.
