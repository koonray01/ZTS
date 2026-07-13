# ctl-live-event-review

        ## Purpose
        Review a significant watcher event and request only necessary tools.

        ## Allowed tools
        - get_current_state
- list_entry_candidates
- build_codex_job

        ## Required output
        What changed, impact, next action and whether Part 3 is warranted.

        ## Prohibited
        - Do not modify raw evidence.
        - Do not change deterministic outputs.
        - Do not place, modify, cancel or close orders.
        - Do not grant permission outside `run_part3`.
        - Do not change policies or skill versions.
