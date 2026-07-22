---
name: ctl-market-analysis-registry
description: Use when a user requests current or live market analysis, a market update, Zenith plus external or both-system comparison, or Scalping or Daytrade setups that must be recorded and auditable.
---

# Market Analysis Registry

Use one fresh, read-only evidence chain and one canonical Registry history. This is the primary route for every applicable request, even when the user does not ask to record it.

## Run the foreground workflow

1. Invoke `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1` for a new current/live request. Never reuse an earlier snapshot as fresh.
2. Require connected MT5, `source=LIVE_MT5`, fresh evidence, QC PASS, `trade_write_enabled=false`, and `auto_execution_enabled=false`. Stop live interpretation when evidence fails.
3. Bind the Zenith view to that snapshot. Add external evidence only when requested; preserve URL, retrieval time, hash, and attribution. External prices never replace the MT5 quote.
4. Keep Zenith and Chat/external conclusions separate. Classify output as `ZENITH_CANDIDATE`, `CONDITIONAL_WATCH_SETUP`, or `NO_SETUP`; never promote a Chat setup into a Candidate.
5. Build a structured `CHAT_MODEL` envelope before the response and freeze it only through an available supported integration. Report the registration path used. If unavailable, report `CHAT_REGISTRATION_BLOCKED`; do not misrepresent launcher capabilities. Incomplete persisted provenance is `EXTERNAL_EVIDENCE_PARTIAL`.
6. Record to `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`. Resolve the implementation checkout from its `registry.json`; never fall back locally. Missing/invalid configuration is `REGISTRY_CONFIG_INVALID`; competing roots are `REGISTRY_PATH_AMBIGUOUS`.
7. Run bounded foreground catch-up and report processed and remaining jobs. On failure preserve valid pending work and report `CATCHUP_BLOCKED`. This is not a background service.

## Report independent gates

Return evidence/quote, Zenith view, requested external view, comparison, setup class, action, Registry/catch-up result, and safety assertion. Expose `analysis_status`, `external_evidence_status`, `registry_recording_status`, `catchup_status`, and `safety_status`, plus immutable IDs and scheduled-job count when available.

Use `PHASE2_ENABLED_NO_EVENTS` when capability exists without outcome events and `INSUFFICIENT_EVIDENCE` when performance cannot be judged. Registry failure is visible (`REGISTRY_BLOCKED`), never silent success.

Assert `order_actions=0` and `permission_leakage=0`. Part 3 remains explicit, deterministic, and separate; analysis, a setup, or a Registry record never grants trading permission or establishes performance efficacy.
