# Canonical Analysis Registry Path Design

## Purpose

Ensure every Zenith analysis session on this workstation writes to one
Analysis Performance Registry, regardless of the Git checkout, worktree,
current directory, or analysis output directory used to start the command.

The canonical runtime root is:

```text
D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry
```

This change governs new writes. Existing ledgers remain immutable until a
separate validated import/replay operation is approved.

## Current Failure

The Phase 2 market-analysis command derives its default registry root from the
analysis output directory:

```python
registry_root = out.parent / "analysis_registry"
```

Relative output paths resolve inside the active checkout. Consequently, a
session running from the primary checkout and one running from a Git worktree
can create independent ledgers. The split is caused by path resolution, not by
an intentional session partition.

## Chosen Architecture

Create one registry-path resolver in `ctl_analysis_registry`. All Registry
CLIs and market-analysis integration code consume the resolver rather than
constructing default paths independently.

The resolver returns one immutable value object containing:

- `root`: the canonical registry directory;
- `ledger`: `<root>/events.jsonl`;
- `sqlite`: `<root>/index.sqlite`;
- `evidence`: `<root>/evidence`;
- `config`: `<root>/registry.json`;
- `lease`: `<root>/writer.lease.json`;
- `operations`: `<root>/operations.jsonl`.

The workstation canonical root is stored in a workspace-level runtime
configuration outside every Git checkout. A workspace-level launcher loads
that configuration and invokes the canonical implementation. The resolver
must not depend on `cwd`, repository root, output directory, branch name,
worktree location, session ID, or inherited environment variables.

The workspace-level files are:

```text
D:\MyWork\AlgoTrade\OS\Zenith Trading System\
|-- runtime\analysis_registry\
|   |-- registry.json
|   |-- events.jsonl
|   |-- index.sqlite
|   |-- writer.lease.json
|   `-- evidence\
`-- tools\run_zenith_analysis.ps1
```

`registry.json` identifies the canonical root, configuration schema version,
and expected Registry producer version. It contains configuration only and is
not part of the append-only event chain.

## Resolution and Override Rules

1. With no Registry path arguments, use the workspace-configured canonical
   root.
2. `--registry-root` is the normal explicit override. The resolver derives the
   ledger, SQLite, evidence, configuration, operation-log, and lease paths
   beneath that root.
3. Individual path overrides are migration/diagnostic-only. If supported by a
   command, every path that command mutates must be supplied and the command
   must declare the non-canonical mode in its output.
4. A partial mutation-path override is a configuration error and must stop
   before creating the analysis output directory, capturing MT5 evidence, or
   writing any Registry file.
5. All resolved paths are converted to absolute normalized paths.
6. A default resolved inside a Git worktree or analysis output directory is a
   configuration error; the tool must not silently create a fallback Registry.
7. The analysis output directory remains independent of Registry storage.
8. Read-only tools may inspect an explicitly named ledger or index without
   requiring an evidence path, but must label the operation non-canonical when
   it is outside the configured root.

Environment variables are not the authoritative default because different
sessions may inherit different environments. A future deployment may support
an explicit environment override, but it is outside this change.

## Integration Points

The following entry points must use the shared resolver:

- `tools/update_market_analysis.py`;
- `tools/record_analysis_registry.py`;
- `tools/rebuild_analysis_registry.py`;
- `tools/verify_analysis_registry.py`;
- Phase 2 registration/catch-up integration where paths are constructed.
- the workspace-level `tools/run_zenith_analysis.ps1` launcher.

Each command must report the absolute resolved Registry root, canonical versus
non-canonical mode, configuration schema version, and producer version in its
summary so an operator can audit where data was read or written.

The workspace launcher is the stable entry point for natural-language Zenith
analysis. It selects the canonical implementation independently of the
caller's checkout and always supplies the configured `--registry-root`. Skill
and `AGENTS.md` instructions must route Registry-producing analysis through
this launcher. Direct execution from an unpatched historical checkout is not a
supported canonical write path and must not be described as standardized.

## Concurrency and Integrity

Multiple sessions may now target the same ledger. Every mutating operation,
including standalone record, integrated registration/catch-up, backfill, and
SQLite rebuild, must participate in one coordination protocol rooted at
`writer.lease.json`. Lease ownership, expiry, stale recovery, operation log,
and release semantics must be consistent across these entry points. A writer
that cannot acquire the lease must fail visibly; it must never create a
session-local Registry as a fallback.

The resolver and configuration validation run before `out.mkdir`, MT5 capture,
or any other command-side filesystem mutation. Lease acquisition happens
immediately before the first Registry mutation and covers the complete ledger
append plus SQLite rebuild transaction boundary. Read-only verification does
not acquire the writer lease.

The SQLite file remains a rebuildable read model. Replacement of the canonical
SQLite index must occur only while holding the same writer lease used for
ledger mutation. The JSONL ledger and evidence store remain authoritative. No
implementation step may concatenate, overwrite, or edit an existing ledger.

## Legacy Registry Handling

At implementation time, inventory known non-canonical Registries and report
them without mutation. At minimum, the inventory currently includes Registries
under the primary checkout, the `live-analysis-main` worktree, and `D:\zreg`.

Combining these histories is a separate migration task. It must:

- verify each source hash chain;
- detect duplicate and conflicting stable IDs;
- replay accepted events through the Registry writer;
- preserve source provenance;
- rebuild and verify the canonical SQLite index;
- retain original ledgers unchanged.

## Failure Handling

The system fails closed when configuration is missing, malformed, partially
overridden, or resolves to an unsafe session-local location. Error output must
show the rejected resolved paths and the configured canonical root without
creating analysis output, capturing MT5 evidence, or writing an event, index,
or evidence file.

No failure may trigger MT5 writes, broker actions, Permission/Part 3, or a
fallback Registry.

## Test Design

Automated tests must prove that:

- primary-checkout and worktree working directories resolve identically;
- different analysis output parents resolve identically;
- session IDs do not influence Registry paths;
- the default returns the configured absolute root and every defined child
  path;
- `--registry-root` produces the complete canonical path set;
- a permitted complete migration override is accepted and labeled;
- a partial mutation-path override fails before any filesystem mutation or
  MT5 adapter call;
- a session-local fallback is rejected;
- every Registry CLI and market-analysis integration uses the resolver;
- standalone recorder, integrated registration/catch-up, backfill, and index
  rebuild contend on the same writer lease;
- concurrent-writer failure does not create another Registry or replace the
  SQLite index;
- the workspace launcher selects the same canonical implementation and root
  when called from the primary checkout and a worktree;
- output reports configuration and producer versions;
- existing Registry and analysis tests continue to pass.

Tests use temporary directories and must not append to the live canonical
ledger.

## Acceptance Criteria

The change is accepted when two dry-run analyses launched from different Git
worktrees and different output directories report the exact same canonical
Registry paths, no new `analysis_registry` directory appears beneath either
output tree, partial overrides fail without output creation or MT5 adapter
invocation, all mutating tools demonstrate common lease contention, and the
Registry test suite passes.

The workspace launcher and runtime configuration must exist outside the Git
worktrees before acceptance. The canonical branch, Registry skill, and
`AGENTS.md` must direct new sessions to the launcher. Historical unpatched
tools are retained for reproducibility but are not authorized as canonical
writers.

The acceptance run must remain read-only with respect to MT5 and broker state.

## Out of Scope

- automatic background analysis;
- broker execution or order management;
- changing Registry event semantics or scoring;
- importing or deleting legacy Registry files;
- sharing this workstation Registry over a network;
- selecting a cross-machine storage service.
- modifying every historical branch or archived source pack.
