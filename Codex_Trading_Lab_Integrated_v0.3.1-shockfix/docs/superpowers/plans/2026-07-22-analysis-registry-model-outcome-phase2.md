# Analysis Registry Model Outcome Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build restart-safe model-outcome evaluation for frozen Zenith and Chat Model decisions, including directional, scenario, setup, and abstention outcomes, coverage reports, bounded automatic catch-up, and an optional read-only worker.

**Architecture:** Extend the Phase 1 append-only JSONL ledger with backward-compatible typed Phase 2 events. A rebuildable SQLite projection schedules due work; source-bound follow-up evidence feeds deterministic labelers, while reports remain rebuildable artifacts. Normal analysis freezes current decisions before bounded catch-up, and no component can affect trading permission or broker state.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `datetime`, `enum`, `fcntl`/Windows file APIs through portable exclusive-create leases, `hashlib`, `json`, `sqlite3`), `jsonschema>=4.20`, `pytest>=8.0`, existing MT5 snapshot adapter.

## Global Constraints

- JSONL is the append-only source of truth and is never rewritten during normal operation.
- Existing `ANALYSIS_REGISTRY_EVENT_V0_1` events and hashes remain valid without migration.
- Only source-bound bars with valid temporal and QC coverage may resolve outcomes.
- `ZENITH` and `CHAT_MODEL` remain separate systems and performance denominators.
- Phase 2 V1 uses `DIRECTIONAL_TERMINAL_ATR_V1` and `SINGLE_TARGET` setup scoring.
- Conditional decisions bind activation-time reference price and ATR; unconditional decisions bind decision-time values.
- Routine reports are rebuildable; only explicit immutable publication appends `REPORT_PUBLISHED`.
- Core completion does not depend on tick-history availability or the optional worker.
- `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0` are invariant.
- No Phase 2 report may claim validated edge, tune policy, or open a promotion gate.

---

## File Structure

### New schemas

- `schemas/frozen_model_decision.schema.json`: canonical frozen decision and activation contracts.
- `schemas/evaluation_job.schema.json`: durable horizon job states and terminal reasons.
- `schemas/followup_evidence.schema.json`: source-bound bars, QC matrix, price-quality tier, and manifest bindings.
- `schemas/model_outcome.schema.json`: typed directional, scenario, setup, and abstention outcomes.
- `schemas/analysis_coverage_report.schema.json`: deterministic coverage report contract.
- `schemas/analysis_performance_report.schema.json`: deterministic performance report contract.

### New package modules

- `src/ctl_analysis_registry/contracts.py`: enums, typed schema validation, and event payload dispatch.
- `src/ctl_analysis_registry/lease.py`: single-writer lease acquisition, heartbeat, release, and stale recovery.
- `src/ctl_analysis_registry/scheduler.py`: stable job identity and lifecycle projection.
- `src/ctl_analysis_registry/followup.py`: source-bound historical evidence collection and QC.
- `src/ctl_analysis_registry/directional.py`: `DIRECTIONAL_TERMINAL_ATR_V1` labeler.
- `src/ctl_analysis_registry/scenario.py`: canonical ordered-event scenario labeler.
- `src/ctl_analysis_registry/setup.py`: `SINGLE_TARGET` setup labeler and M1 ambiguity refinement.
- `src/ctl_analysis_registry/abstention.py`: frozen-control WAIT/HOLD/ABSTAIN labeler.
- `src/ctl_analysis_registry/reporting.py`: coverage, performance, Wilson interval, and semantic deduplication.
- `src/ctl_analysis_registry/catchup.py`: bounded lease-protected orchestration.
- `src/ctl_analysis_registry/worker.py`: optional foreground worker and persisted control state.

### Modified package modules

- `src/ctl_analysis_registry/events.py`: mixed-version envelope construction and hash compatibility.
- `src/ctl_analysis_registry/ledger.py`: fsynced append and partial-tail fail-closed checks.
- `src/ctl_analysis_registry/index.py`: Phase 2 projection tables and metadata.
- `src/ctl_analysis_registry/recorder.py`: Zenith and Chat Model frozen envelopes.
- `src/ctl_analysis_registry/verify.py`: multi-version payload validation, projection-head parity, and safety checks.
- `src/ctl_analysis_registry/__init__.py`: public Phase 2 interfaces.
- `tools/update_market_analysis.py`: freeze the current analysis, then run bounded catch-up.

### New operator tools

- `tools/catch_up_analysis_registry.py`
- `tools/analysis_registry_status.py`
- `tools/build_analysis_performance_report.py`
- `tools/run_analysis_outcome_worker.py`

---

### Task 1: Backward-Compatible Phase 2 Event and Decision Contracts

**Files:**
- Create: `schemas/frozen_model_decision.schema.json`
- Create: `schemas/evaluation_job.schema.json`
- Create: `schemas/followup_evidence.schema.json`
- Create: `schemas/model_outcome.schema.json`
- Create: `src/ctl_analysis_registry/contracts.py`
- Modify: `schemas/analysis_registry_event.schema.json`
- Modify: `src/ctl_analysis_registry/events.py`
- Modify: `src/ctl_analysis_registry/verify.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry_phase2_contracts.py`

**Interfaces:**
- Consumes: Phase 1 `build_event`, `event_hash`, `validate_event_chain`, and JSON Schema validation conventions.
- Produces: `validate_phase2_payload(event_type: str, payload: dict) -> list[str]`, `build_v2_event(fields: dict, previous_hash: str | None) -> dict`, and canonical event names `DECISION_FROZEN`, `EVALUATION_JOB_SCHEDULED`, `DECISION_ACTIVATED`, `FOLLOWUP_EVIDENCE_RECORDED`, `MODEL_OUTCOME_RECORDED`, `REPORT_PUBLISHED`.

- [ ] **Step 1: Write failing mixed-version and frozen-contract tests**

```python
def test_v1_and_v2_events_share_one_valid_hash_chain(tmp_path):
    v1 = build_event(_v1_fields(), previous_hash=None)
    decision = _frozen_directional(system="CHAT_MODEL", subtype="CONDITIONAL_DIRECTIONAL")
    v2 = build_v2_event(_v2_fields("DECISION_FROZEN", decision), previous_hash=v1["event_hash"])
    assert validate_event_chain([v1, v2]) == []
    assert validate_phase2_payload("DECISION_FROZEN", decision) == []


def test_conditional_contract_requires_activation_method_and_atr_config():
    decision = _frozen_directional(system="CHAT_MODEL", subtype="CONDITIONAL_DIRECTIONAL")
    decision.pop("activation")
    assert "activation is required" in validate_phase2_payload("DECISION_FROZEN", decision)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_contracts.py -v`

Expected: FAIL because `contracts.py`, `build_v2_event`, and the new schemas do not exist.

- [ ] **Step 3: Add exact contract constants and validation dispatch**

```python
V2_SCHEMA_VERSION = "ANALYSIS_REGISTRY_EVENT_V0_2"
PHASE2_EVENT_TYPES = {
    "DECISION_FROZEN",
    "EVALUATION_JOB_SCHEDULED",
    "DECISION_ACTIVATED",
    "FOLLOWUP_EVIDENCE_RECORDED",
    "MODEL_OUTCOME_RECORDED",
    "REPORT_PUBLISHED",
}
DECISION_TYPES = {"DIRECTIONAL", "SCENARIO", "SETUP", "ABSTENTION"}
SYSTEMS = {"ZENITH", "CHAT_MODEL"}


def validate_phase2_payload(event_type: str, payload: dict[str, object]) -> list[str]:
    schema_name = {
        "DECISION_FROZEN": "frozen_model_decision.schema.json",
        "EVALUATION_JOB_SCHEDULED": "evaluation_job.schema.json",
        "DECISION_ACTIVATED": "frozen_model_decision.schema.json",
        "FOLLOWUP_EVIDENCE_RECORDED": "followup_evidence.schema.json",
        "MODEL_OUTCOME_RECORDED": "model_outcome.schema.json",
    }.get(event_type)
    if schema_name is None:
        return []
    return schema_errors(schema_name, payload)
```

The decision schema must require system, identity fields, decision subtype, horizons, policy version, source bindings, safety flags, statistical identities, and either decision-time reference/ATR or a frozen activation method/ATR configuration.

- [ ] **Step 4: Preserve V1 hashing while adding explicit V2 construction**

```python
def build_v2_event(fields: dict[str, Any], *, previous_hash: str | None) -> dict[str, Any]:
    event = {
        "schema_version": V2_SCHEMA_VERSION,
        **fields,
        "previous_event_hash": previous_hash,
    }
    event["event_hash"] = event_hash(event)
    return event
```

Update verification to select the envelope schema by `schema_version` and typed payload schema by `event_type`; do not alter V1 event bytes or hashes.

- [ ] **Step 5: Run contract and Phase 1 regression tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_contracts.py tests/test_analysis_registry.py -v`

Expected: PASS; a mixed V1/V2 chain validates and all Phase 1 tests remain green.

- [ ] **Step 6: Commit the contract slice**

```powershell
git add schemas/analysis_registry_event.schema.json schemas/frozen_model_decision.schema.json schemas/evaluation_job.schema.json schemas/followup_evidence.schema.json schemas/model_outcome.schema.json src/ctl_analysis_registry/contracts.py src/ctl_analysis_registry/events.py src/ctl_analysis_registry/verify.py src/ctl_analysis_registry/__init__.py tests/test_analysis_registry_phase2_contracts.py
git commit -m "feat: add phase two registry contracts"
```

---

### Task 2: Fsynced Ledger Append, Writer Lease, and Rebuildable Phase 2 Projection

**Files:**
- Create: `src/ctl_analysis_registry/lease.py`
- Modify: `src/ctl_analysis_registry/ledger.py`
- Modify: `src/ctl_analysis_registry/index.py`
- Modify: `src/ctl_analysis_registry/verify.py`
- Test: `tests/test_analysis_registry_phase2_storage.py`

**Interfaces:**
- Consumes: V2 event contracts from Task 1.
- Produces: `RegistryWriterLease.acquire(path, owner_id, ttl_seconds)`, `AppendOnlyLedger.append_fsynced(event)`, `rebuild_index(ledger_path, sqlite_path)` with `projection_metadata`, `frozen_decisions`, `evaluation_jobs`, `followup_evidence`, and `model_outcomes` tables.

- [ ] **Step 1: Write failing storage and concurrency tests**

```python
def test_second_live_writer_cannot_acquire_registry_lease(tmp_path):
    lease_path = tmp_path / "registry.lease.json"
    first = RegistryWriterLease.acquire(lease_path, "owner-a", ttl_seconds=30)
    with pytest.raises(LeaseBusyError):
        RegistryWriterLease.acquire(lease_path, "owner-b", ttl_seconds=30)
    first.release()


def test_rebuilt_projection_binds_to_ledger_head(tmp_path):
    ledger, sqlite = _ledger_with_phase2_events(tmp_path)
    counts = rebuild_index(ledger, sqlite)
    metadata = sqlite3.connect(sqlite).execute(
        "SELECT projection_schema_version, ledger_head_hash FROM projection_metadata"
    ).fetchone()
    assert metadata == ("ANALYSIS_REGISTRY_PROJECTION_V0_2", _last_hash(ledger))
    assert counts["evaluation_jobs"] == 1
```

- [ ] **Step 2: Run tests and confirm missing lease/storage behavior**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_storage.py -v`

Expected: FAIL because the lease and Phase 2 projection tables are absent.

- [ ] **Step 3: Implement exclusive-create lease with stale recovery**

```python
@dataclass
class RegistryWriterLease:
    path: Path
    owner_id: str
    acquired_at: datetime
    ttl_seconds: int

    @classmethod
    def acquire(cls, path: Path, owner_id: str, ttl_seconds: int) -> "RegistryWriterLease":
        acquired_at = datetime.now(timezone.utc)
        payload = json.dumps({"owner_id": owner_id, "heartbeat_at": acquired_at.isoformat(), "ttl_seconds": ttl_seconds}).encode()
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return cls(path, owner_id, acquired_at, ttl_seconds)

    def heartbeat(self) -> None:
        current = json.loads(self.path.read_text(encoding="utf-8"))
        if current["owner_id"] != self.owner_id:
            raise LeaseBusyError("registry lease owner changed")
        current["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(current, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    def release(self) -> None:
        current = json.loads(self.path.read_text(encoding="utf-8"))
        if current["owner_id"] == self.owner_id:
            self.path.unlink()
```

Use atomic exclusive file creation. Recovery is allowed only when `heartbeat_at + ttl_seconds < now`; write an auditable recovery record to the operation log before replacing the stale lease.

- [ ] **Step 4: Implement append-one-line, flush, fsync, and partial-tail rejection**

```python
def append_fsynced(self, event: dict[str, Any]) -> None:
    encoded = canonical_json(event).encode("utf-8") + b"\n"
    self.assert_complete_tail()
    with self.path.open("ab", buffering=0) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if self.read_all()[-1]["event_hash"] != event["event_hash"]:
        raise LedgerError("appended event hash verification failed")
```

- [ ] **Step 5: Add V2 projection tables and atomic SQLite publication**

Build into `index.sqlite.tmp`, verify event hashes/counts and ledger head, close the connection, then use `os.replace`. Store `projection_schema_version` and `ledger_head_hash` in one-row metadata.

- [ ] **Step 6: Run storage, verifier, and Phase 1 tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_storage.py tests/test_analysis_registry.py -v`

Expected: PASS, including lease contention and deterministic rebuild parity.

- [ ] **Step 7: Commit the storage slice**

```powershell
git add src/ctl_analysis_registry/lease.py src/ctl_analysis_registry/ledger.py src/ctl_analysis_registry/index.py src/ctl_analysis_registry/verify.py tests/test_analysis_registry_phase2_storage.py
git commit -m "feat: add durable registry scheduling storage"
```

---

### Task 3: Frozen Decision Recording for Zenith and Chat Model

**Files:**
- Modify: `src/ctl_analysis_registry/recorder.py`
- Create: `src/ctl_analysis_registry/chat_model.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry_phase2_recording.py`

**Interfaces:**
- Consumes: `build_v2_event`, contract validation, fsynced ledger append, existing Decision Core packets.
- Produces: `freeze_zenith_decisions(decision_state, snapshot, analysis_id) -> list[dict]`, `freeze_chat_model_view(envelope, snapshot) -> list[dict]`, and `record_frozen_decisions(ledger, decisions) -> list[str]`.

- [ ] **Step 1: Write failing attribution, identity, and revision tests**

```python
def test_zenith_and_chat_model_have_separate_system_ids():
    zenith = freeze_zenith_decisions(_decision_state(), _snapshot(), "ANALYSIS_1")
    chat = freeze_chat_model_view(_chat_envelope(), _snapshot())
    assert {row["system"] for row in zenith} == {"ZENITH"}
    assert {row["system"] for row in chat} == {"CHAT_MODEL"}
    assert zenith[0]["prediction_family_id"] != chat[0]["prediction_family_id"]


def test_material_revision_gets_new_decision_id():
    original = _frozen_decision(direction="BULLISH")
    revised = revise_decision(original, {"direction": "BEARISH"}, revision_time=_before_start())
    assert revised["revision_type"] == "MATERIAL_REVISION"
    assert revised["decision_id"] != original["decision_id"]
```

- [ ] **Step 2: Run tests and confirm recording APIs are missing**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_recording.py -v`

Expected: FAIL on missing recording functions.

- [ ] **Step 3: Implement deterministic statistical and decision identities**

```python
prediction_family_id = stable_id("PREDICTION_FAMILY", analysis_id, system, decision_type, semantic_root)
decision_id = stable_id("DECISION_V2", prediction_family_id, variant_id, horizon_set_hash, policy_version)
semantic_opportunity_id = candidate.get("semantic_candidate_id") or scenario.get("opportunity_group_id")
```

Freeze `ZENITH` scenarios/candidates only when measurable fields exist. Mark legacy or incomplete conclusions `NON_SCORABLE` with explicit reasons.

- [ ] **Step 4: Implement structured Chat Model envelope validation**

```python
def freeze_chat_model_view(envelope: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    assert envelope["snapshot_id"] == snapshot["snapshot_id"]
    assert envelope["system"] == "CHAT_MODEL"
    return [freeze_one_claim(claim, snapshot) for claim in envelope["claims"]]
```

The envelope must be produced in the same response path and cannot be reconstructed from prior prose.

- [ ] **Step 5: Enforce revision timing**

Return a new decision for a material pre-start revision. Return an audit-only correction for changes at or after `evaluation_start`; never mutate the original decision.

- [ ] **Step 6: Run recording and Phase 1 tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_recording.py tests/test_analysis_registry.py -v`

Expected: PASS with separate Zenith/Chat Model identities and no regression.

- [ ] **Step 7: Commit the recording slice**

```powershell
git add src/ctl_analysis_registry/recorder.py src/ctl_analysis_registry/chat_model.py src/ctl_analysis_registry/__init__.py tests/test_analysis_registry_phase2_recording.py
git commit -m "feat: freeze zenith and chat model decisions"
```

---

### Task 4: Durable Scheduler and Conditional Activation

**Files:**
- Create: `src/ctl_analysis_registry/scheduler.py`
- Test: `tests/test_analysis_registry_phase2_scheduler.py`

**Interfaces:**
- Consumes: frozen decisions and SQLite Phase 2 projection.
- Produces: `schedule_jobs(decision) -> list[dict]`, `due_jobs(connection, now, limit) -> list[dict]`, `activate_conditional(decision, closed_bars) -> dict | None`, and lifecycle states `PENDING`, `WAITING_ACTIVATION`, `DUE`, `RETRY_PENDING`, `EVIDENCE_COLLECTED`, `LABELED`, plus terminal reasons.

- [ ] **Step 1: Write failing stable-job and activation-clock tests**

```python
def test_conditional_job_clock_starts_at_activation_close():
    decision = _conditional_decision(horizon="PT1H", activation_level=4061.0)
    activation = activate_conditional(decision, [_bar(open_time="10:00", close_time="10:05", close=4062.0)])
    assert activation["evaluation_start"] == "2026-07-22T10:05:00Z"
    assert activation["evaluation_deadline"] == "2026-07-22T11:05:00Z"
    assert activation["evaluation_reference_price_method"] == "ACTIVATION_BAR_CLOSE_MID"


def test_same_decision_horizon_policy_has_stable_job_id():
    jobs = schedule_jobs(_unconditional_decision(horizons=["PT15M", "PT1H"]))
    assert jobs[0]["job_id"] == schedule_jobs(_unconditional_decision(horizons=["PT15M", "PT1H"]))[0]["job_id"]
```

- [ ] **Step 2: Run scheduler tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_scheduler.py -v`

Expected: FAIL because scheduler APIs are absent.

- [ ] **Step 3: Implement ISO-8601 duration parsing and stable job identity**

```python
job_id = stable_id("EVALUATION_JOB", decision_id, horizon, labeling_policy_version)
```

Support `PT15M`, `PT1H`, `PT4H`, and `P1D`; reject trade-style words without an explicit duration mapping frozen in the decision.

- [ ] **Step 4: Implement closed-bar activation and expiry**

Use the same canonical event grammar as scenarios. Bind activation close mid, ATR value/configuration, evaluation start/deadline, and source bar IDs in `DECISION_ACTIVATED`. If activation expiry passes first, terminalize as `EXPIRED_UNTRIGGERED`.

- [ ] **Step 5: Implement due query, retry state, and max work limit**

`due_jobs` must sort by deadline then job ID. Temporary history failures increment attempt count and set `RETRY_PENDING`; exhausted retries map to explicit `INSUFFICIENT_FOLLOWUP` or `UNRESOLVABLE`, never a negative trading outcome.

- [ ] **Step 6: Run scheduler tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_scheduler.py -v`

Expected: PASS for restart-stable job IDs, activation timing, expiry, and retries.

- [ ] **Step 7: Commit the scheduler slice**

```powershell
git add src/ctl_analysis_registry/scheduler.py tests/test_analysis_registry_phase2_scheduler.py
git commit -m "feat: schedule durable model outcome jobs"
```

---

### Task 5: Source-Bound Follow-up Evidence and QC Matrix

**Files:**
- Create: `src/ctl_analysis_registry/followup.py`
- Modify: `src/ctl_mt5_snapshot/adapter.py`
- Test: `tests/test_analysis_registry_phase2_followup.py`

**Interfaces:**
- Consumes: due job, frozen snapshot bindings, `MetaTrader5SnapshotAdapter` historical rates/ticks.
- Produces: `collect_followup(job, adapter, output_root) -> dict`, `eligible_bars(job, bars) -> list[dict]`, `cross_snapshot_qc(decision, evidence) -> dict`, and price-quality tiers.

- [ ] **Step 1: Write failing eligibility, closure, history-conflict, and price-tier tests**

```python
def test_bar_containing_evaluation_start_is_excluded():
    job = _job(start="10:03", deadline="11:03", timeframe="M5")
    bars = [_bar("10:00", "10:05"), _bar("10:05", "10:10")]
    assert [b["open_time"] for b in eligible_bars(job, bars)] == ["2026-07-22T10:05:00Z"]


def test_weekend_bar_outside_terminal_lag_is_not_used():
    job = _job(deadline="2026-07-24T21:00:00Z", max_terminal_lag_seconds=300)
    result = select_terminal_bar(job, [_bar("2026-07-26T22:00:00Z", "2026-07-26T22:05:00Z")])
    assert result == {"status": "INSUFFICIENT_FOLLOWUP", "reason": "MARKET_CLOSURE_NO_TERMINAL_BAR"}


def test_changed_overlap_fingerprint_blocks_outcome():
    qc = cross_snapshot_qc(_decision(overlap_hash="aaa"), _evidence(overlap_hash="bbb"))
    assert qc["status"] == "FAIL"
    assert "EVIDENCE_CONFLICT" in qc["reasons"]
```

- [ ] **Step 2: Run follow-up tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_followup.py -v`

Expected: FAIL because follow-up collection APIs are absent.

- [ ] **Step 3: Add read-only historical adapter methods**

```python
def closed_bars_between(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]:
    return self._history_between(symbol=symbol, timeframe=timeframe, start=start, end=end, include_ticks=False)

def ticks_between(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
    return self._history_between(symbol=symbol, timeframe="TICK", start=start, end=end, include_ticks=True)
```

Implement `_history_between` in the same adapter using `copy_rates_range` for bars and `copy_ticks_range` with `COPY_TICKS_ALL` for ticks, applying the capture-scoped broker offset and the existing bar dictionary fields. These methods must never call order APIs. Tick retrieval failure returns unavailable evidence and does not block Core closed-bar collection.

- [ ] **Step 4: Implement temporal selection and terminal-lag policy**

Require `bar.open_time >= evaluation_start` and terminal close no later than deadline plus one source-timeframe duration. Record known closure separately from corrupt/missing history.

- [ ] **Step 5: Implement source binding and price reconstruction**

Verify server, source class, symbol, digits, point, broker offset, and overlapping-bar fingerprint. Treat rates as bid OHLC; reconstruct ask using `spread_points * point`. Emit `TRUE_BID_ASK_TICKS`, `BAR_SPREAD_RECONSTRUCTED`, or `MID_ONLY_PROXY` without mixing cohorts.

- [ ] **Step 6: Persist immutable evidence bundle**

Write bars/ticks to temporary files, hash them, atomically rename, then write a manifest containing job ID, source bindings, QC matrix, and raw hashes.

- [ ] **Step 7: Run follow-up and snapshot regression tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_followup.py tests/test_snapshot_symbol_spec.py tests/test_sprint10_snapshot_harness.py -v`

Expected: PASS with no broker-write behavior.

- [ ] **Step 8: Commit the evidence slice**

```powershell
git add src/ctl_analysis_registry/followup.py src/ctl_mt5_snapshot/adapter.py tests/test_analysis_registry_phase2_followup.py
git commit -m "feat: collect outcome blind followup evidence"
```

---

### Task 6: Directional and Ordered Scenario Labelers

**Files:**
- Create: `src/ctl_analysis_registry/directional.py`
- Create: `src/ctl_analysis_registry/scenario.py`
- Test: `tests/test_analysis_registry_phase2_directional.py`
- Test: `tests/test_analysis_registry_phase2_scenario.py`

**Interfaces:**
- Consumes: frozen decision, activated values when conditional, and eligible follow-up evidence.
- Produces: `label_directional(decision, job, evidence) -> dict` and `label_scenario(decision, job, evidence) -> dict`.

- [ ] **Step 1: Write failing directional threshold tests**

```python
@pytest.mark.parametrize((terminal, expected), [(100.30, "CORRECT"), (99.70, "INCORRECT"), (100.10, "NEUTRAL")])
def test_directional_terminal_atr_v1(terminal, expected):
    decision = _directional(direction="BULLISH", reference=100.0, atr=1.0)
    assert label_directional(decision, _job(), _evidence(terminal_mid=terminal))["classification"] == expected


def test_conditional_uses_activation_values_not_decision_values():
    decision = _conditional_directional(decision_mid=95.0, decision_atr=5.0)
    job = _activated_job(reference_mid=100.0, activation_atr=1.0)
    result = label_directional(decision, job, _evidence(terminal_mid=100.3))
    assert result["classification"] == "CORRECT"
```

- [ ] **Step 2: Write failing scenario order and ambiguity tests**

```python
def test_required_scenario_steps_must_complete_in_order():
    decision = _scenario([_closed_above(101), _touched_band(102, 103)])
    evidence = _events([_touch(102.5, at="10:05"), _close(101.5, at="10:10")])
    assert label_scenario(decision, _job(), evidence)["classification"] == "UNRESOLVED"


def test_provable_invalidation_precedence_wins():
    result = label_scenario(_scenario_with_invalidation(), _job(), _invalidation_first_evidence())
    assert result["classification"] == "INVALIDATED"
```

- [ ] **Step 3: Run both test files and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_directional.py tests/test_analysis_registry_phase2_scenario.py -v`

Expected: FAIL because labelers are absent.

- [ ] **Step 4: Implement `DIRECTIONAL_TERMINAL_ATR_V1` exactly**

```python
signed_return_atr = direction_sign * (terminal_mid - evaluation_reference_mid) / evaluation_atr
classification = "CORRECT" if signed_return_atr >= 0.25 else "INCORRECT" if signed_return_atr <= -0.25 else "NEUTRAL"
```

Return MFE/MAE diagnostics, policy version, horizon, QC eligibility, and evidence refs. Evidence conflict returns `AMBIGUOUS`; invalid input remains excluded.

- [ ] **Step 5: Implement the canonical scenario event evaluator**

Support only `CLOSED_ABOVE`, `CLOSED_BELOW`, `TOUCHED_BAND`, `ENTERED_BAND`, `EXITED_BAND`, and `INVALIDATION_HIT`. Enforce required-step order and provable precedence. Never parse scenario prose.

- [ ] **Step 6: Run labeler tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_directional.py tests/test_analysis_registry_phase2_scenario.py -v`

Expected: PASS for thresholds, activation values, event order, partial confirmation, expiry, and ambiguity.

- [ ] **Step 7: Commit both labelers**

```powershell
git add src/ctl_analysis_registry/directional.py src/ctl_analysis_registry/scenario.py tests/test_analysis_registry_phase2_directional.py tests/test_analysis_registry_phase2_scenario.py
git commit -m "feat: label directional and scenario outcomes"
```

---

### Task 7: Single-Target Setup and Abstention Labelers

**Files:**
- Create: `src/ctl_analysis_registry/setup.py`
- Create: `src/ctl_analysis_registry/abstention.py`
- Test: `tests/test_analysis_registry_phase2_setup.py`
- Test: `tests/test_analysis_registry_phase2_abstention.py`

**Interfaces:**
- Consumes: frozen setup/control and follow-up evidence with price-quality tier.
- Produces: `label_setup(decision, evidence) -> dict`, `refine_same_bar(decision, evidence) -> dict`, and `label_abstention(decision, control_outcome) -> dict`.

- [ ] **Step 1: Write failing side-aware setup tests**

```python
def test_buy_entry_uses_ask_and_target_uses_bid():
    setup = _buy_setup(entry=100.0, stop=99.0, scoring_target=102.0)
    evidence = _bid_ask_path(ask_lows=[100.0], bid_highs=[102.0], bid_lows=[99.5])
    result = label_setup(setup, evidence)
    assert result["classification"] == "TP_FIRST"
    assert result["realized_r"] == 2.0


def test_one_m1_bar_touching_tp_and_sl_stays_ambiguous():
    result = label_setup(_buy_setup(), _one_bar_hits_both(price_quality="BAR_SPREAD_RECONSTRUCTED"))
    assert result["classification"] == "AMBIGUOUS_SAME_BAR"
```

- [ ] **Step 2: Write failing abstention eligibility tests**

```python
def test_general_hold_without_frozen_control_is_not_scorable():
    assert label_abstention(_hold_without_control(), None)["classification"] == "NOT_SCORABLE"


def test_rejected_candidate_that_would_hit_sl_is_protected_from_loss():
    control = _resolved_control("SL_FIRST")
    assert label_abstention(_hold_with_frozen_control(), control)["classification"] == "PROTECTED_FROM_LOSS"
```

- [ ] **Step 3: Run setup and abstention tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_abstention.py -v`

Expected: FAIL because setup and abstention labelers are absent.

- [ ] **Step 4: Implement `SINGLE_TARGET` setup scoring**

Require one entry, stop, scoring target, and expiry. Additional targets remain excursion milestones. BUY uses ask for entry and bid for exits; SELL uses bid for entry and ask for exits. `MID_ONLY_PROXY` cannot resolve a setup.

- [ ] **Step 5: Implement M1 then optional tick precedence refinement**

If a source-timeframe bar touches both boundaries, inspect source-bound M1 bars. If one M1 bar still touches both, use `TRUE_BID_ASK_TICKS` when available; otherwise return `AMBIGUOUS_SAME_BAR`.

- [ ] **Step 6: Implement frozen-control abstention mapping**

Map resolved control outcomes to `PROTECTED_FROM_LOSS`, `MISSED_WINNER`, `CORRECT_PATIENCE`, `UNNECESSARY_DELAY`, or `NO_MATERIAL_OPPORTUNITY`. No frozen control means `NOT_SCORABLE`.

- [ ] **Step 7: Run labeler tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_abstention.py -v`

Expected: PASS for side-aware prices, TP/SL precedence, R metrics, target milestones, and abstention controls.

- [ ] **Step 8: Commit the setup/abstention slice**

```powershell
git add src/ctl_analysis_registry/setup.py src/ctl_analysis_registry/abstention.py tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_abstention.py
git commit -m "feat: label setup and abstention outcomes"
```

---

### Task 8: Coverage and Performance Reporting

**Files:**
- Create: `schemas/analysis_coverage_report.schema.json`
- Create: `schemas/analysis_performance_report.schema.json`
- Create: `src/ctl_analysis_registry/reporting.py`
- Create: `tools/build_analysis_performance_report.py`
- Test: `tests/test_analysis_registry_phase2_reporting.py`

**Interfaces:**
- Consumes: SQLite Phase 2 projections and immutable evidence refs.
- Produces: `build_coverage_report(connection, cohort_filter) -> dict`, `build_performance_report(connection, cohort_filter) -> dict`, `wilson_interval(successes, total, z=1.959963984540054) -> tuple[float, float]`, and explicit report publication.

- [ ] **Step 1: Write failing denominator, deduplication, and threshold tests**

```python
def test_setup_headline_deduplicates_variants_by_semantic_opportunity():
    rows = [_setup_outcome("OPP_1", "EARLY", "TP_FIRST"), _setup_outcome("OPP_1", "FULL", "TP_FIRST")]
    report = build_performance_report(_connection(rows), {"system": "ZENITH"})
    assert report["setup"]["raw_variant_count"] == 2
    assert report["setup"]["unique_opportunity_count"] == 1


def test_horizons_and_systems_never_share_denominator():
    report = build_performance_report(_mixed_rows(), {})
    assert set(report["directional"]["cohorts"]) == {"ZENITH|PT15M", "ZENITH|PT1H", "CHAT_MODEL|PT1H"}


def test_expectancy_is_not_headline_before_thirty_triggered_setups():
    report = build_performance_report(_connection(_resolved_setups(29)), {"system": "ZENITH"})
    assert report["setup"]["headline_status"] == "INSUFFICIENT_EVIDENCE"
```

- [ ] **Step 2: Run reporting tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_reporting.py -v`

Expected: FAIL because reporting module and schemas are absent.

- [ ] **Step 3: Implement coverage reconciliation**

Report total, pending, resolved, invalid input, insufficient, ambiguous, non-scorable, excluded, integrity tier, source, system, decision type, horizon, and QC-reason counts. Assert that categories reconcile exactly to Registry jobs.

- [ ] **Step 4: Implement Wilson intervals and separate metric families**

Use one-vs-rest binary rates for directional correctness and each scenario/setup classification. Keep systems and horizons separate. Publish numerator, denominator, unresolved/excluded counts, and Wilson 95% interval.

- [ ] **Step 5: Implement semantic opportunity headline deduplication**

Keep variant diagnostics, but count one unique semantic opportunity in headline setup metrics using a deterministic representative rule frozen in the report policy: FULL confirmation, then CONTINUATION, then EARLY confirmation, then lexical variant ID.

- [ ] **Step 6: Add CLI and explicit immutable publication**

The CLI writes rebuildable JSON reports by default. `--publish-ledger` appends only a `REPORT_PUBLISHED` event with report hash, cohort ID, policy versions, generation time, and evidence refs.

- [ ] **Step 7: Run reporting tests and schema validation**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_reporting.py -v`

Expected: PASS with exact reconciliation and no edge/promotion claim.

- [ ] **Step 8: Commit the reporting slice**

```powershell
git add schemas/analysis_coverage_report.schema.json schemas/analysis_performance_report.schema.json src/ctl_analysis_registry/reporting.py tools/build_analysis_performance_report.py tests/test_analysis_registry_phase2_reporting.py
git commit -m "feat: report model outcome performance"
```

---

### Task 9: Bounded Catch-up Orchestrator and Operator CLIs

**Files:**
- Create: `src/ctl_analysis_registry/catchup.py`
- Create: `tools/catch_up_analysis_registry.py`
- Create: `tools/analysis_registry_status.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Test: `tests/test_analysis_registry_phase2_catchup.py`

**Interfaces:**
- Consumes: lease, scheduler, follow-up collector, typed labelers, ledger, and index.
- Produces: `run_catchup(ledger_path, sqlite_path, evidence_root, adapter, now, max_jobs) -> dict` and `registry_status(sqlite_path, now) -> dict`.

- [ ] **Step 1: Write failing restart, idempotency, and bounded-work tests**

```python
def test_overdue_jobs_resolve_after_restart(tmp_path):
    paths = _registry_with_due_job(tmp_path)
    first = run_catchup(**paths, adapter=_adapter(), now=_after_deadline(), max_jobs=10)
    second = run_catchup(**paths, adapter=_adapter(), now=_after_deadline(), max_jobs=10)
    assert first["resolved"] == 1
    assert second["resolved"] == 0
    assert second["duplicate_outcomes"] == 0


def test_max_jobs_returns_partial_with_remaining_count(tmp_path):
    result = run_catchup(**_registry_with_due_jobs(tmp_path, 3), adapter=_adapter(), now=_now(), max_jobs=1)
    assert result["status"] == "PARTIAL"
    assert result["processed"] == 1
    assert result["remaining"] == 2
```

- [ ] **Step 2: Run catch-up tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_catchup.py -v`

Expected: FAIL because orchestration APIs are absent.

- [ ] **Step 3: Implement lease-protected bounded catch-up**

Verify ledger/index, acquire the single-writer lease, process sorted due jobs up to `max_jobs`, persist evidence, append material lifecycle/outcome events, rebuild/replace SQLite, release lease, and return `COMPLETE`, `PARTIAL`, `DEFERRED`, or `BLOCKED`.

- [ ] **Step 4: Enforce idempotency and retry noise policy**

Before appending an outcome, query stable `(decision_id, horizon, original_policy_version)` identity. Append only material lifecycle transitions; write transient attempt details to operation logs rather than the ledger.

- [ ] **Step 5: Implement catch-up and status CLIs**

```powershell
$env:PYTHONPATH='src'
python tools/catch_up_analysis_registry.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite --evidence outputs/analysis_registry/evidence --max-jobs 25
python tools/analysis_registry_status.py --sqlite outputs/analysis_registry/index.sqlite
```

Both commands print JSON and assert all trading safety flags are false/zero.

- [ ] **Step 6: Run catch-up, storage, and labeler tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_catchup.py tests/test_analysis_registry_phase2_storage.py tests/test_analysis_registry_phase2_directional.py tests/test_analysis_registry_phase2_scenario.py tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_abstention.py -v`

Expected: PASS with restart-safe, bounded, duplicate-free operation.

- [ ] **Step 7: Commit the catch-up slice**

```powershell
git add src/ctl_analysis_registry/catchup.py src/ctl_analysis_registry/__init__.py tools/catch_up_analysis_registry.py tools/analysis_registry_status.py tests/test_analysis_registry_phase2_catchup.py
git commit -m "feat: run bounded model outcome catchup"
```

---

### Task 10: Normal Analysis Integration and Optional Background Worker

**Files:**
- Modify: `tools/update_market_analysis.py`
- Modify: `tools/run_chat_analysis.py`
- Create: `src/ctl_analysis_registry/worker.py`
- Create: `tools/run_analysis_outcome_worker.py`
- Test: `tests/test_analysis_registry_phase2_integration.py`
- Test: `tests/test_analysis_registry_phase2_worker.py`

**Interfaces:**
- Consumes: frozen recording APIs and `run_catchup`.
- Produces: analysis result fields `registry_recording_status`, `catchup_status`, `catchup_processed`, `catchup_remaining`; optional `run_worker(config, stop_file) -> dict`.

- [ ] **Step 1: Write failing analysis-order and unregistered-status tests**

```python
def test_current_analysis_is_frozen_before_bounded_catchup(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(route, "record_current_analysis", lambda *a, **k: calls.append("record"))
    monkeypatch.setattr(route, "run_catchup", lambda *a, **k: calls.append("catchup") or _catchup_result())
    result = route.run(_args(tmp_path))
    assert calls == ["record", "catchup"]
    assert result["registry_recording_status"] == "RECORDED"


def test_registry_integrity_failure_keeps_read_only_analysis_but_marks_unregistered():
    result = _run_with_broken_registry()
    assert result["snapshot_id"]
    assert result["registry_recording_status"] == "ANALYSIS_NOT_REGISTERED"
    assert result["trade_write_enabled"] is False
```

- [ ] **Step 2: Write failing worker lease and restart tests**

```python
def test_worker_defers_when_analysis_command_holds_lease(tmp_path):
    with _held_registry_lease(tmp_path):
        result = run_worker(_worker_config(tmp_path, cycles=1), stop_file=tmp_path / "stop")
    assert result["status"] == "DEFERRED"


def test_worker_restart_processes_persisted_due_jobs(tmp_path):
    _create_due_job(tmp_path)
    first = run_worker(_worker_config(tmp_path, cycles=0), stop_file=tmp_path / "stop")
    second = run_worker(_worker_config(tmp_path, cycles=1), stop_file=tmp_path / "stop")
    assert first["processed"] == 0
    assert second["processed"] == 1
```

- [ ] **Step 3: Run integration/worker tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_worker.py -v`

Expected: FAIL because the routes do not register/catch up and the worker is absent.

- [ ] **Step 4: Integrate freeze-then-catch-up into normal analysis**

After fresh snapshot and Decision Core output, record Zenith and optional Chat Model envelopes under the lease. Then call bounded catch-up. If Registry integrity or recording fails, keep the market analysis read-only and return `ANALYSIS_NOT_REGISTERED`; never reconstruct it later from prose.

- [ ] **Step 5: Implement optional foreground worker**

The worker loops for configured cycles/interval, calls `run_catchup`, heartbeats its control state, and consumes a local stop file. Use no background process launcher inside the core module; the operator chooses how to keep the CLI running.

- [ ] **Step 6: Run integration, chat safety, and worker tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_worker.py tests/test_chat_cli.py tests/test_chat_safety_contract.py -v`

Expected: PASS with `PHASE2_CORE_COMPLETE` independent of worker availability.

- [ ] **Step 7: Commit integration and worker**

```powershell
git add tools/update_market_analysis.py tools/run_chat_analysis.py src/ctl_analysis_registry/worker.py tools/run_analysis_outcome_worker.py tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_worker.py
git commit -m "feat: integrate outcome catchup with analysis"
```

---

### Task 11: Conservative Backfill and End-to-End Acceptance Audit

**Files:**
- Create: `src/ctl_analysis_registry/backfill.py`
- Create: `tools/backfill_analysis_registry_phase2.py`
- Create: `tools/audit_analysis_registry_phase2.py`
- Create: `reports/market_analysis_accuracy/PHASE2_ACCEPTANCE_TEMPLATE.md`
- Test: `tests/test_analysis_registry_phase2_backfill.py`
- Test: `tests/test_analysis_registry_phase2_acceptance.py`

**Interfaces:**
- Consumes: existing Phase 1 ledger, source artifacts, all Phase 2 components.
- Produces: `classify_legacy_decision(event: dict, source_bundle: dict) -> str`, `backfill_eligible(event: dict, source_bundle: dict, ledger_path: Path, dry_run: bool) -> dict`, and immutable acceptance audit with Core/Worker gates.

- [ ] **Step 1: Write failing no-hindsight backfill tests**

```python
def test_phase1_scenario_without_machine_readable_criteria_is_non_scorable():
    assert classify_legacy_decision(_phase1_scenario(), _source_bundle()) == "NON_SCORABLE_LEGACY"


def test_quarantined_legacy_snapshot_is_invalid_input():
    assert classify_legacy_decision(_phase1_setup(), _quarantined_bundle()) == "INVALID_INPUT"


def test_backfill_never_parses_chat_prose_for_levels():
    result = backfill_eligible(_chat_only_event(), _bundle_with_future_chart())
    assert result["classification"] == "NON_SCORABLE_LEGACY"
    assert result["created_decisions"] == 0
```

- [ ] **Step 2: Write failing end-to-end acceptance test**

```python
def test_phase2_core_acceptance_reconciles_and_has_zero_safety_leakage(tmp_path):
    result = run_acceptance_fixture(tmp_path)
    assert result["core_gate"] == "PHASE2_CORE_COMPLETE"
    assert result["ledger_index_parity"] is True
    assert result["duplicate_outcomes"] == 0
    assert result["order_actions"] == 0
    assert result["permission_leakage"] == 0
```

- [ ] **Step 3: Run backfill and acceptance tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_backfill.py tests/test_analysis_registry_phase2_acceptance.py -v`

Expected: FAIL because backfill and acceptance tools are absent.

- [ ] **Step 4: Implement conservative legacy classification**

Return only `BACKFILL_ELIGIBLE`, `NON_SCORABLE_LEGACY`, `INVALID_INPUT`, or `INSUFFICIENT_EVIDENCE`. Eligibility requires a pre-outcome frozen measurable contract and source evidence; no prose parsing or retrospective geometry creation is allowed.

- [ ] **Step 5: Implement idempotent backfill CLI**

Require `--dry-run` by default and an explicit `--append-eligible` flag under the writer lease. Print counts and proposed event IDs before mutation. Re-running must append zero duplicates.

- [ ] **Step 6: Implement acceptance audit CLI**

Audit all 31 design criteria: mixed-version verification, hash/index parity, scheduling/restart, typed outcomes, QC exclusions, cohort separation, semantic deduplication, report thresholds, automatic integration, optional worker status, and zero trading safety leakage. Write JSON plus a Markdown summary using the committed template.

- [ ] **Step 7: Run the complete Phase 2 suite**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_contracts.py tests/test_analysis_registry_phase2_storage.py tests/test_analysis_registry_phase2_recording.py tests/test_analysis_registry_phase2_scheduler.py tests/test_analysis_registry_phase2_followup.py tests/test_analysis_registry_phase2_directional.py tests/test_analysis_registry_phase2_scenario.py tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_abstention.py tests/test_analysis_registry_phase2_reporting.py tests/test_analysis_registry_phase2_catchup.py tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_worker.py tests/test_analysis_registry_phase2_backfill.py tests/test_analysis_registry_phase2_acceptance.py -v`

Expected: PASS.

- [ ] **Step 8: Run full repository verification**

Run: `$env:PYTHONPATH='src'; python -m pytest -q`

Expected: PASS with no Phase 1, Decision Core, MT5 snapshot, chat, permission, zone, value, or worker regression.

Run: `$env:PYTHONPATH='src'; python tools/validate_contracts.py`

Expected: exit code 0.

- [ ] **Step 9: Run read-only acceptance on fresh output paths**

```powershell
$env:PYTHONPATH='src'
python tools/audit_analysis_registry_phase2.py --ledger outputs/analysis_registry/events.jsonl --sqlite outputs/analysis_registry/index.sqlite --output outputs/analysis_registry/phase2_acceptance
```

Expected: `PHASE2_CORE_COMPLETE`, ledger/index parity true, and all trading safety counters zero. Worker gate may remain `NOT_RUN` without blocking Core.

- [ ] **Step 10: Commit backfill and acceptance audit**

```powershell
git add src/ctl_analysis_registry/backfill.py tools/backfill_analysis_registry_phase2.py tools/audit_analysis_registry_phase2.py reports/market_analysis_accuracy/PHASE2_ACCEPTANCE_TEMPLATE.md tests/test_analysis_registry_phase2_backfill.py tests/test_analysis_registry_phase2_acceptance.py
git commit -m "feat: complete model outcome phase two audit"
```

---

## Execution Checkpoints

- After Task 2: review mixed-version hash safety, fsync behavior, lease recovery, and SQLite parity before adding domain logic.
- After Task 5: review one real read-only MT5 evidence bundle and verify broker time, bar open/close times, spread reconstruction, and overlap fingerprints.
- After Task 7: review typed outcome semantics using fixed fixtures before building aggregate metrics.
- After Task 9: run restart/idempotency review before integrating catch-up into normal analysis.
- After Task 10: verify current analysis still succeeds read-only when Registry mutation is blocked.
- After Task 11: publish the immutable acceptance audit only after the full suite and safety checks pass.
