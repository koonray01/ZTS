# ctl-part3-preexecute

        ## Purpose
        Run and explain deterministic Part 3.

        ## Allowed tools
        - list_entry_candidates
- run_part3
- explain_decision

        ## Required output
        APPROVED/WAIT/REJECTED/INVALIDATED with gate details.

        ## Prohibited
        - Do not modify raw evidence.
        - Do not change deterministic outputs.
        - Do not place, modify, cancel or close orders.
        - Do not grant permission outside `run_part3`.
        - Do not change policies or skill versions.
