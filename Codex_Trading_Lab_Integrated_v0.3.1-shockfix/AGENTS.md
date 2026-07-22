# Codex Operating Contract — Integrated Repository

## Boundary and safety

- This repository is independent from TradingOS main. Do not share or modify its runtime state, stores, locks, policies, or code without explicit authorization.
- All trading workflows are manual and read-only: no broker placement, modification, cancellation, close, SL/TP writes, or automatic execution.
- Require connected MT5, `source=LIVE_MT5`, freshness, QC, session state, locks, `trade_write_enabled=false`, and `auto_execution_enabled=false` before current-market interpretation.
- UNKNOWN stays UNKNOWN; AI cannot override deterministic FAIL/BLOCK. Opportunity is not Permission.
- Part 3 is explicit and only for a valid `READY_FOR_PERMISSION_REVIEW` Candidate. APPROVED means Manual Review Only.
- Preserve immutable evidence and append-only journals; never auto-promote research into policy.

## One primary route

Choose one primary route per user intent:

1. Current/live analysis, update, Zenith plus external/both comparison, Scalping, or Daytrade setup: `ctl-market-analysis-registry`.
2. Historical performance or evidence audit: `ctl-evidence-audit`.
3. Position monitoring or live-event review: `ctl-live-event-review`.
4. Explicit Part 3: `ctl-part3-preexecute`, after deterministic eligibility checks.

Domain skills may be consulted but must not restart orchestration, capture another snapshot, or duplicate Registry writes. Applicable current analysis records automatically; the user need not request registration.

## Canonical live history

- Invoke `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1` for Registry-producing live analysis.
- The sole live root is `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`; never derive it from a checkout, worktree, output directory, or chat session.
- Resolve the implementation checkout from `runtime/analysis_registry/registry.json`. Invalid configuration is `REGISTRY_CONFIG_INVALID`; competing roots are `REGISTRY_PATH_AMBIGUOUS`. Never create a local fallback or claim audit continuity after failure.
- Catch-up is bounded foreground work during a request, not a daemon.

## Evidence precedence

Locked policy → deterministic checker → validated evidence → validated research → episode observation → AI interpretation → hypothesis. External evidence cannot override Candidate, Risk, Permission, QC, or safety gates.

## Development

Read `docs/00_SYSTEM_OVERVIEW.md` and `reports/KNOWN_GAPS.md`; run `python -m pytest -q` and `python tools/run_all_validation.py --output outputs/integrated_validation`. Current integration status: `PREPARED_NOT_LIVE_INTEGRATED`; do not claim live readiness or a validated edge without real forward evidence.
