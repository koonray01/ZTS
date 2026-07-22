# ctl-market-read

        ## Purpose
        Summarize the compact market state without inventing facts.

        ## Canonical Registry route
        For current-market analysis that records results, invoke
        `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`.
        Never derive Registry storage from cwd, checkout, worktree, session ID,
        or the analysis output directory. Never fall back to a local Registry.

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
