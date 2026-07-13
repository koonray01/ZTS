---
document_version: 0.2.0
status: LOCKED_FOR_SPRINT1
project: Codex Trading Lab
owner: evidence_owner
last_updated: 2026-07-12
---

# Evidence and Append-Only Policy

## Directory contract

```text
data/evidence/raw/<YYYY>/<MM>/<DD>/<run_id>/
data/evidence/normalized/<YYYY>/<MM>/<DD>/<run_id>/
data/evidence/quarantine/<YYYY>/<MM>/<DD>/<run_id>/
data/manifests/<run_id>.manifest.json
data/state/latest_snapshot_pointer.json
```

## Raw evidence rules
1. Raw evidence is written once.
2. A raw path must never be overwritten.
3. Existing raw content with a mismatched hash causes `QUARANTINE`.
4. Files are first written to a temporary sibling path, flushed, then atomically renamed.
5. Each file receives SHA-256, byte size, media type, role, producer version, and source timestamp in the run manifest.
6. Derived data references raw hashes and does not replace raw evidence.
7. Deletion is forbidden during ordinary operation. Retention is a separate approved maintenance task.

## Run manifest minimum fields
- contract/schema version,
- run ID and request ID,
- source (`LIVE_MT5`, `REPLAY`, `FIXTURE`),
- terminal identity,
- symbol and timeframes,
- broker and capture time,
- component versions,
- file list and SHA-256,
- QC decision,
- warnings/errors,
- previous-manifest hash when chaining is enabled.

## Latest state pointer
`latest_snapshot_pointer.json` may be replaced atomically because it is a pointer, not evidence. It contains only the latest immutable snapshot ID/path/hash.

## Quarantine conditions
- hash mismatch,
- path traversal,
- duplicate run ID with changed content,
- mixed symbol/account/run,
- mixed-time snapshot,
- missing required role,
- malformed schema,
- source labeled LIVE without MT5 runtime evidence.

## Auditability
Every analytical result must be traceable to a snapshot and its manifest without relying on Codex conversation history.
