# Analysis Performance Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1 of the Analysis Performance Registry: validated stable identities, append-only JSONL events, Zenith ingestion, integrity verification, and a rebuildable SQLite read model.

**Architecture:** Existing Zenith snapshots and reports remain immutable source evidence. A new focused `ctl_analysis_registry` package emits hash-chained registry events to JSONL, validates them fail-closed, and rebuilds a disposable SQLite index. Outcome labeling, External/Comparison ingestion, historical migration, dashboards, and upgrade gates are intentionally deferred to later plans.

**Tech Stack:** Python >=3.11, standard library (`dataclasses`, `hashlib`, `json`, `sqlite3`, `pathlib`, `typing`), existing `jsonschema>=4.20`, pytest>=8.0, and the repository's existing schema/CLI conventions.

## Global Constraints

- Manual Only: no broker writes, no order placement, no Permission authority, and no execution-state mutation.
- Existing raw evidence, session bundles, snapshots, manifests, and prior ledger events are immutable.
- `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0` remain explicit safety assertions where applicable.
- JSONL is canonical registry evidence; SQLite is a rebuildable read index and never the source of truth.
- Re-ingestion is idempotent; corrections and supersessions append new events rather than overwriting old events.
- Source classes `LIVE_MT5`, `REPLAY`, `SYNTHETIC`, and `CHAT_ONLY` remain distinct; integrity tiers are `VERIFIED`, `PARTIAL`, `CHAT_ONLY`, and `UNMATCHED`.
- Do not include outcome labels, performance metrics, historical migration, External/Comparison ingestion, or auto-upgrade policy in Phase 1.
- Preserve the existing dirty worktree: stage only files belonging to the current task when committing.

---

## File Map

Create these focused units:

- `schemas/analysis_registry_event.schema.json`: JSON Schema for one hash-chained event.
- `schemas/analysis_registry_bundle.schema.json`: JSON Schema for the recorder's ingestion bundle.
- `src/ctl_analysis_registry/__init__.py`: public exports only.
- `src/ctl_analysis_registry/identity.py`: deterministic ID and canonical JSON helpers.
- `src/ctl_analysis_registry/events.py`: event construction and hash-chain validation.
- `src/ctl_analysis_registry/ledger.py`: append-only JSONL writer/reader and idempotency checks.
- `src/ctl_analysis_registry/recorder.py`: Zenith artifact-to-event conversion and bundle validation.
- `src/ctl_analysis_registry/index.py`: SQLite schema, rebuild, and read queries.
- `src/ctl_analysis_registry/verify.py`: fail-closed bundle/ledger/index verification.
- `tools/record_analysis_registry.py`: read-only CLI to record an existing Zenith output directory.
- `tools/rebuild_analysis_registry.py`: read-only CLI to rebuild SQLite from the ledger.
- `tools/verify_analysis_registry.py`: read-only CLI for integrity and safety verification.
- `tests/test_analysis_registry.py`: unit, contract, idempotency, rebuild, and safety tests.
- `docs/06_EVIDENCE_COLLECTION_GUIDE.md`: add the registry directory and immutable-reference rules.

Do not modify the existing Decision Core, Permission Agent, MT5 adapter, or execution code in Phase 1.

## Interfaces Between Tasks

The implementation uses these exact Python interfaces:

```python
# identity.py
def canonical_json(value: object) -> str: ...
def stable_id(prefix: str, *parts: str) -> str: ...
def sha256_hex(value: str | bytes) -> str: ...

# events.py
def build_event(payload: dict[str, object], *, previous_hash: str | None) -> dict[str, object]: ...
def event_hash(event: dict[str, object]) -> str: ...
def validate_event_chain(events: list[dict[str, object]]) -> list[str]: ...

# ledger.py
class AppendOnlyLedger:
    def append(self, event: dict[str, object]) -> str: ...
    def read_all(self) -> list[dict[str, object]]: ...
    def contains_event(self, event_id: str) -> bool: ...

# recorder.py
def record_zenith_output(output_dir: Path, ledger: AppendOnlyLedger) -> dict[str, object]: ...

# index.py
def rebuild_index(ledger_path: Path, sqlite_path: Path) -> dict[str, int]: ...

# verify.py
def verify_registry(ledger_path: Path, sqlite_path: Path | None = None) -> dict[str, object]: ...
```

## Task 1: Define Registry Schemas and Canonical Identity

**Files:**
- Create: `schemas/analysis_registry_event.schema.json`
- Create: `schemas/analysis_registry_bundle.schema.json`
- Create: `src/ctl_analysis_registry/__init__.py`
- Create: `src/ctl_analysis_registry/identity.py`
- Test: `tests/test_analysis_registry.py`

**Interfaces:**
- Produces `canonical_json`, `stable_id`, and `sha256_hex` for the event layer.
- Schemas are consumed by Tasks 2–5 and must reject unknown top-level fields.

- [ ] **Step 1: Write failing identity and schema tests.**

Add tests that assert canonical JSON sorts object keys and uses compact separators, `stable_id("ANALYSIS", "XAUUSD", "T0")` is deterministic, different parts produce different IDs, and a valid bundle passes `jsonschema.validate` while a bundle with an unknown top-level field fails.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "identity or schema" -q
```

Expected: collection or import failure because `ctl_analysis_registry.identity` and the new schemas do not exist.

- [ ] **Step 3: Implement canonical identity helpers and schemas.**

`identity.py` must serialize mappings with `sort_keys=True`, `separators=(",", ":")`, and UTF-8; `stable_id` must hash the NUL-separated string parts and return `PREFIX_<first 24 uppercase hex characters>`; `sha256_hex` must return the full lowercase SHA-256 hex digest.

`analysis_registry_event.schema.json` must require `schema_version`, `event_id`, `event_type`, `event_time`, `decision_time`, `source_class`, `integrity_tier`, `producer`, `payload`, `previous_event_hash`, and `event_hash`. Enumerate Phase 1 event types: `ANALYSIS_RECORDED`, `VIEW_RECORDED`, `DECISION_RECORDED`, `CANDIDATE_STATUS_CHANGED`, `OUTCOME_LABEL_PENDING`, `MANUAL_TRADE_RECORDED`, `CORRECTION_APPENDED`, and `SUPERSESSION_APPENDED`.

`analysis_registry_bundle.schema.json` must require `schema_version`, `analysis_id`, `source_class`, `integrity_tier`, `analysis`, `views`, `decisions`, and `evidence_refs`; allow one or more views, require each view to have `view_id` and `system` (`ZENITH` or `EXTERNAL`), and require each decision to have `decision_id`, `decision_type`, `action`, `scorable`, and `horizons`.

- [ ] **Step 4: Run the focused tests to verify they pass.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "identity or schema" -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the schema/identity unit.**

```text
git add schemas/analysis_registry_event.schema.json schemas/analysis_registry_bundle.schema.json src/ctl_analysis_registry/__init__.py src/ctl_analysis_registry/identity.py tests/test_analysis_registry.py
git commit -m "feat: define analysis registry identities and schemas"
```

## Task 2: Implement Hash-Chained Events and Append-only JSONL Ledger

**Files:**
- Create: `src/ctl_analysis_registry/events.py`
- Create: `src/ctl_analysis_registry/ledger.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry.py`

**Interfaces:**
- Consumes identity helpers and the event schema from Task 1.
- Produces `build_event`, `event_hash`, `validate_event_chain`, and `AppendOnlyLedger` for recorder/index/verification tasks.

- [ ] **Step 1: Write failing event and ledger tests.**

Test that the first event has `previous_event_hash=None`, the next event references the prior event hash, changing payload changes `event_hash`, a tampered line produces a chain error, append of the same `event_id` is idempotent, and append of the same ID with different content raises a deterministic duplicate-collision error without changing the file.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "event or ledger" -q
```

Expected: FAIL because event and ledger implementations are absent.

- [ ] **Step 3: Implement event construction and ledger.**

`build_event` must copy the payload, set `schema_version="ANALYSIS_REGISTRY_EVENT_V0_1"`, calculate `event_hash` over the canonical event content excluding `event_hash`, and never include nondeterministic fields in the hash input. `validate_event_chain` must return explicit error strings for malformed JSON, duplicate IDs, broken previous hash, and hash mismatch.

`AppendOnlyLedger.append` must create parent directories, use UTF-8 JSONL with one object per line, flush and `os.fsync` before returning, read the last hash for the next event, and compare canonical content when an event ID already exists. It must expose `read_all` and `contains_event` without mutating the ledger.

- [ ] **Step 4: Run the focused tests to verify they pass.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "event or ledger" -q
```

Expected: all selected tests pass, including tamper and duplicate-collision cases.

- [ ] **Step 5: Commit the ledger unit.**

```text
git add src/ctl_analysis_registry/__init__.py src/ctl_analysis_registry/events.py src/ctl_analysis_registry/ledger.py tests/test_analysis_registry.py
git commit -m "feat: add append-only analysis registry ledger"
```

## Task 3: Record Zenith Outputs as Validated Registry Events

**Files:**
- Create: `src/ctl_analysis_registry/recorder.py`
- Create: `tools/record_analysis_registry.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry.py`

**Interfaces:**
- Consumes `AppendOnlyLedger`, identity helpers, and a Zenith output directory containing `snapshot.json`, `decision_state.json`, `candidate_delta.json`, and `evidence/`.
- Produces `record_zenith_output(output_dir, ledger) -> dict` with `analysis_id`, `event_ids`, `integrity_tier`, `source_class`, `evidence_refs`, and `safety`.

- [ ] **Step 1: Write failing recorder tests.**

Create a temporary fixture with a valid snapshot, decision state, candidate delta, and manifest. Test that recording emits one `ANALYSIS_RECORDED`, one `VIEW_RECORDED`, one `DECISION_RECORDED` per declared decision, and candidate lifecycle events for candidate deltas; all events share one `analysis_id`, reference the snapshot ID, and carry `safety={"trade_write_enabled": False, "auto_execution_enabled": False, "order_actions": 0, "permission_leakage": 0}`. Test a missing manifest becomes `PARTIAL` and does not enter a `VERIFIED` result. Test recording the same output twice returns identical IDs and ledger line count.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "recorder" -q
```

Expected: FAIL because `record_zenith_output` and its CLI do not exist.

- [ ] **Step 3: Implement read-only Zenith ingestion.**

The recorder must load JSON only; it must never write inside the source output directory. Bind `analysis_id` to the source snapshot ID, capture/decision time, symbol, and source class using `stable_id`. Use `LIVE_MT5` only when the snapshot says `source="LIVE_MT5"`; otherwise preserve the declared source. Map a complete manifest and valid snapshot/decision evidence to `VERIFIED`; missing or invalid bindings map to `PARTIAL` or `UNMATCHED` with reason codes.

Emit the analysis event first, then view and decision events, followed by candidate delta events. Preserve raw Zenith candidate status and `SUPPRESSED/UNKNOWN` exactly; never convert it into expiry or invalidation. Include source paths, snapshot ID, manifest ID/hash, and evidence references in payloads. The CLI must accept `--output-dir`, `--ledger`, and `--source-class` (defaulting to the source-declared class), print a compact JSON result, and exit nonzero on schema/integrity failure without writing broker state.

- [ ] **Step 4: Run the focused tests and a real read-only fixture.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "recorder" -q
python tools/record_analysis_registry.py --output-dir outputs/market_update_20260720_160414 --ledger outputs/analysis_registry/events.jsonl
```

Expected: selected tests pass; the CLI reports a stable `analysis_id`, `LIVE_MT5` source, the source integrity tier, and all safety flags false/zero. It must not alter the source output directory.

- [ ] **Step 5: Commit the recorder unit.**

```text
git add src/ctl_analysis_registry/__init__.py src/ctl_analysis_registry/recorder.py tools/record_analysis_registry.py tests/test_analysis_registry.py
git commit -m "feat: record Zenith analysis evidence"
```

## Task 4: Build Rebuildable SQLite Read Model

**Files:**
- Create: `src/ctl_analysis_registry/index.py`
- Create: `tools/rebuild_analysis_registry.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry.py`

**Interfaces:**
- Consumes the validated JSONL ledger from Task 2 and recorder event payloads from Task 3.
- Produces `rebuild_index(ledger_path, sqlite_path) -> dict[str, int]` and query tables for analyses, views, decisions, events, and evidence references.

- [ ] **Step 1: Write failing SQLite rebuild tests.**

Test that rebuild creates a SQLite database with tables `events`, `analyses`, `views`, `decisions`, and `evidence_refs`; repeated rebuilds produce the same row counts and logical records; a tampered ledger refuses to rebuild; and a query by `analysis_id` returns its source class, integrity tier, decision count, and evidence references.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "index or sqlite" -q
```

Expected: FAIL because the index module and tables do not exist.

- [ ] **Step 3: Implement deterministic SQLite rebuild.**

Create the database in a temporary sibling path, validate the full ledger chain before inserting, use explicit schema DDL with foreign keys, insert events in ledger order, and derive projection rows from event payloads. Replace the destination only after the temporary database commits successfully. Store event hashes and source evidence references so every projection can be traced back.

`rebuild_index` must return counts such as `events`, `analyses`, `views`, `decisions`, and `evidence_refs`. It must not calculate performance outcomes or alter the JSONL ledger.

- [ ] **Step 4: Run focused tests and CLI rebuild.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "index or sqlite" -q
python tools/rebuild_analysis_registry.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite
```

Expected: selected tests pass and the CLI prints deterministic row counts.

- [ ] **Step 5: Commit the index unit.**

```text
git add src/ctl_analysis_registry/__init__.py src/ctl_analysis_registry/index.py tools/rebuild_analysis_registry.py tests/test_analysis_registry.py
git commit -m "feat: add rebuildable analysis registry index"
```

## Task 5: Add Fail-closed Verification and Evidence Documentation

**Files:**
- Create: `src/ctl_analysis_registry/verify.py`
- Create: `tools/verify_analysis_registry.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Modify: `docs/06_EVIDENCE_COLLECTION_GUIDE.md`
- Test: `tests/test_analysis_registry.py`

**Interfaces:**
- Consumes `validate_event_chain`, the JSON schemas, and optional SQLite projections.
- Produces `verify_registry(ledger_path, sqlite_path=None) -> dict` with `status`, `errors`, `warnings`, `counts`, `safety`, and `coverage`.

- [ ] **Step 1: Write failing verification and safety tests.**

Test that a valid ledger/index returns `status="PASS"`, a hash mismatch returns `BLOCKED`, a source bundle with unknown source class returns `BLOCKED`, a bundle missing follow-up fields remains valid for Phase 1 but reports `coverage.outcome_labeling="DEFERRED_PHASE_2"`, and safety flags with any true write/permission value return `BLOCKED`.

- [ ] **Step 2: Run the focused tests to verify they fail.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -k "verify or safety" -q
```

Expected: FAIL because the verifier and CLI do not exist.

- [ ] **Step 3: Implement fail-closed verification.**

`verify_registry` must validate every JSONL event against the event schema, validate the hash chain, optionally compare SQLite event hashes and row counts to the ledger, inspect source/integrity distributions, and assert the safety contract. It must distinguish `PASS`, `CONDITIONAL`, and `BLOCKED`; missing outcomes are a Phase 2 deferred capability, not a Phase 1 error. The CLI must print JSON, return exit code 0 only for `PASS` or explicitly non-blocking `CONDITIONAL`, and never modify the ledger or source artifacts.

Update the evidence guide with the registry directory contract, append-only rules, source/integrity tier meanings, rebuild command, verification command, and the explicit statement that a registry record is an audit trail rather than evidence of trading edge.

- [ ] **Step 4: Run all registry tests and contract checks.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -q
python tools/verify_analysis_registry.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite
python tools/validate_contracts.py
```

Expected: all registry tests pass, the verifier reports `PASS` for the generated fixture, and existing contract validation remains green.

- [ ] **Step 5: Commit the verifier/documentation unit.**

```text
git add src/ctl_analysis_registry/__init__.py src/ctl_analysis_registry/verify.py tools/verify_analysis_registry.py docs/06_EVIDENCE_COLLECTION_GUIDE.md tests/test_analysis_registry.py
git commit -m "feat: verify analysis registry integrity and safety"
```

## Task 6: Phase 1 Integration Verification and Handoff

**Files:**
- Modify: `tests/test_analysis_registry.py` only if an integration assertion is missing.
- Create: `reports/analysis_registry_phase1_validation.md`

**Interfaces:**
- Consumes all Phase 1 modules and the committed design specification.
- Produces an immutable validation report containing commands, counts, safety flags, and known Phase 2 deferrals.

- [ ] **Step 1: Run the complete targeted and repository validation suites.**

Run:

```text
python -m pytest tests/test_analysis_registry.py -q
python -m pytest -q
python tools/run_all_validation.py --output outputs/analysis_registry_phase1_validation
```

Expected: registry tests pass; the repository suite either passes or reports only pre-existing failures with exact test names; integrated validation produces a fresh output directory and retains `order_actions=0` and `permission_leakage=0`.

- [ ] **Step 2: Inspect the generated registry and verify replayability.**

Run the record, rebuild, and verify CLIs against one recent `LIVE_MT5` output and one fixture. Rebuild the SQLite index to a second path and compare `verify_registry` counts and event hashes. Confirm the source output directories have no changed files.

- [ ] **Step 3: Write the Phase 1 validation report.**

Include exact command lines, commit IDs, event/analysis/view/decision counts, source and integrity distributions, SQLite rebuild parity, test results, safety assertions, and explicit deferrals: outcome labels, External/Comparison ingestion, historical migration, dashboards, and upgrade gates.

- [ ] **Step 4: Perform final diff and status review.**

Run:

```text
git diff --check
git status --short
git diff --stat HEAD~6..HEAD -- src/ctl_analysis_registry schemas/analysis_registry* tools/*analysis_registry* tests/test_analysis_registry.py docs/06_EVIDENCE_COLLECTION_GUIDE.md reports/analysis_registry_phase1_validation.md
```

Expected: no whitespace errors; only intended Phase 1 files appear in the task commits; unrelated pre-existing worktree changes remain untouched.

- [ ] **Step 5: Commit the validation report.**

```text
git add reports/analysis_registry_phase1_validation.md
git commit -m "test: validate analysis registry phase one"
```

## Self-review Checklist

- Spec coverage: identity, append-only events, Zenith ingestion, immutable evidence, idempotency, SQLite rebuild, fail-closed validation, safety, and Phase 1 boundary are covered by Tasks 1–6.
- Deferred items are explicit: no outcome labeling, performance metrics, historical migration, External/Comparison ingestion, dashboard, or upgrade gate implementation in this plan.
- Interface consistency: `AppendOnlyLedger` is created in Task 2, consumed by Task 3; `record_zenith_output` is consumed by the Phase 1 CLI flow; `rebuild_index` is consumed by Task 4 CLI and Task 6; `verify_registry` is consumed by Task 5 CLI and Task 6.
- Placeholder scan: this plan contains no unfinished markers or vague implementation steps.
- Safety review: all commands are read-only with respect to broker state; source evidence is never overwritten; only explicitly named task files may be staged.
