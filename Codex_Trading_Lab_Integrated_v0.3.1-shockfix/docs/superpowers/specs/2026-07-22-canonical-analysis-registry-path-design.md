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
- `evidence`: `<root>/evidence`.

The workstation canonical root is stored in a versioned configuration file as
an absolute Windows path. The resolver must not depend on `cwd`, repository
root, output directory, branch name, worktree location, or session ID.

## Resolution and Override Rules

1. With no Registry path arguments, use the configured canonical root.
2. Explicit override is accepted only when ledger, SQLite, and evidence paths
   are all supplied together.
3. A partial override is a configuration error and must stop before any write.
4. All resolved paths are converted to absolute normalized paths.
5. A default resolved inside a Git worktree or analysis output directory is a
   configuration error; the tool must not silently create a fallback Registry.
6. The analysis output directory remains independent of Registry storage.
7. Read-only tools may receive an explicit complete path set for controlled
   verification or migration, but normal live analysis uses the canonical
   default.

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

Each command should report the absolute resolved Registry root in its summary
so an operator can audit where data was read or written.

## Concurrency and Integrity

Multiple sessions may now target the same ledger. The canonical path change
must preserve the existing append-only and writer-lease rules. A writer that
cannot acquire the lease must fail visibly; it must never create a session-
local Registry as a fallback.

The SQLite file remains a rebuildable read model. The JSONL ledger and evidence
store remain authoritative. No implementation step may concatenate, overwrite,
or edit an existing ledger.

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
writing an event, index, or evidence file.

No failure may trigger MT5 writes, broker actions, Permission/Part 3, or a
fallback Registry.

## Test Design

Automated tests must prove that:

- primary-checkout and worktree working directories resolve identically;
- different analysis output parents resolve identically;
- session IDs do not influence Registry paths;
- the default returns the configured absolute root and its three children;
- a complete explicit override is accepted;
- a partial override fails before filesystem mutation;
- a session-local fallback is rejected;
- every Registry CLI and market-analysis integration uses the resolver;
- concurrent-writer failure does not create another Registry;
- existing Registry and analysis tests continue to pass.

Tests use temporary directories and must not append to the live canonical
ledger.

## Acceptance Criteria

The change is accepted when two dry-run analyses launched from different Git
worktrees and different output directories report the exact same canonical
Registry paths, no new `analysis_registry` directory appears beneath either
output tree, partial overrides fail without mutation, and the Registry test
suite passes.

The acceptance run must remain read-only with respect to MT5 and broker state.

## Out of Scope

- automatic background analysis;
- broker execution or order management;
- changing Registry event semantics or scoring;
- importing or deleting legacy Registry files;
- sharing this workstation Registry over a network;
- selecting a cross-machine storage service.
