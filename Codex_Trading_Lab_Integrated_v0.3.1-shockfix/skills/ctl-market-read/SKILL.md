# ctl-market-read

        ## Purpose
        Summarize the compact market state without inventing facts.

        ## Allowed tools
        - get_current_state
- inspect_evidence_refs

        ## Required output
        Current state, conflicts, unknowns and what changed.

        ## Prohibited
        - Do not modify raw evidence.
        - Do not change deterministic outputs.
        - Do not place, modify, cancel or close orders.
        - Do not grant permission outside `run_part3`.
        - Do not change policies or skill versions.
