# Canonical Analysis Registry Validation — 2026-07-22

## Decision

Canonical session-independent routing is validated for supported Zenith
analysis launched through the workspace launcher. Legacy Registries were
inventoried read-only and were not migrated, concatenated, overwritten, or
deleted.

## Canonical Runtime

- Registry root: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`
- Implementation root: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\.worktrees\live-analysis-main\Codex_Trading_Lab_Integrated_v0.3.1-shockfix`
- Mode: `CANONICAL`
- Configuration schema: `ANALYSIS_REGISTRY_CONFIG_V0_1`
- Producer: `CTL_ANALYSIS_REGISTRY_V0_2`
- Trade write: disabled
- Automatic execution: disabled
- Broker order actions: zero

## Verification

The focused Registry acceptance matrix passed: `115 passed in 4.52s`.
Contract validation passed with 39 schemas. Launcher `-ResolveOnly` returned the
same canonical Registry and implementation roots when invoked from the primary
checkout and the linked worktree. The resolve-only path did not call MT5.

Workspace artifact SHA-256:

- `run_zenith_analysis.ps1`: `AFF8B675F4B54FF00AFA90CA859833ABD6ABBA41E6BC48B079D1B0D7156B430E`
- `registry.json`: `864A8CF6936ED079C193FCCE12552B7D6A4E1C109F2E88ACE47997346C236001`

## Legacy Inventory

Inventory reported `mutation_performed=false` and found:

| Registry | Ledger bytes | SHA-256 |
|---|---:|---|
| Worktree `outputs/live_analysis/analysis_registry` | 11,540 | `2A162C66833EDF2F04981FDE6E96A7141CF1628F0FFEEBE82D5791D527A3C2EA` |
| Primary checkout `outputs/analysis_registry` | 694,529 | `CC02C190B6545F0D5278DA8CF392EAD1702E572A05CF72D9832A32EA91473846` |
| `D:\zreg\...\outputs\analysis_registry` | 59,545 | `E7E81B3C7D8EC5BD8C79841D0473712519BBDCB2DB99B31812823058BA42BEF7` |

The new canonical root contains configuration but no ledger or SQLite index
yet. Its first Registry-producing analysis will create those canonical runtime
files while holding `writer.lease.json`.

## Scope Boundary

This validation standardizes new supported writes only. It does not establish
that historical unpatched checkouts are safe canonical writers. It does not
merge legacy history. A future migration must verify each source hash chain,
detect stable-ID conflicts, replay accepted events through the canonical
writer, rebuild the index, and retain source ledgers unchanged.
