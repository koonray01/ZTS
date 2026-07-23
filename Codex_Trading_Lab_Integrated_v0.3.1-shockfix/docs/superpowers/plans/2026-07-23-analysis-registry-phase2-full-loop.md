# Analysis Registry Phase 2 Full-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Phase 2 Analysis Performance Registry loop so native Zenith and structured Chat predictions are normalized, frozen, scheduled, evaluated, rebuilt, audited, and reported without hindsight or broker writes.

**Architecture:** Add one versioned normalization boundary ahead of the existing append-only Registry. Extend the typed ledger and rebuildable SQLite projection before adding scoring, lifecycle, catch-up, cutover, and reporting slices. Every mutable-looking state is derived from immutable events, and every live mutation remains lease-protected and canonical-path validated.

**Tech Stack:** Python 3, pytest, JSON Schema Draft 2020-12, SQLite, JSONL hash-chain ledger, PowerShell launchers.

## Global Constraints

- Canonical live root remains `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`.
- `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0`.
- No broker placement, modification, cancellation, close, SL/TP writes, or automatic execution.
- No persistent background service and no automatic Part 3.
- No hindsight reconstruction or mutation of existing ledger events.
- Legacy records remain in a separate `LEGACY` cohort and never enter headline performance.
- Scalping horizons are `PT15M` and `PT1H`, with headline `PT1H`.
- Daytrade horizons are `PT4H` and `P1D`, with headline `P1D`.
- New native decisions use `normalization_policy_version=PHASE2_NORMALIZATION_V1`.
- Setup range evaluation uses `RANGE_ACTIVATION_SINGLE_TARGET_V2`.
- Directional emission uses `DIRECTIONAL_CLAIM_EMISSION_V1`.
- Unknown remains unknown; missing quote granularity cannot be reconstructed.

---

## File Structure

- Create `src/ctl_analysis_registry/normalizer.py`: translate Zenith and Chat envelopes into frozen Phase 2 contracts.
- Create `src/ctl_analysis_registry/policy.py`: derive policy state and perform lease-protected cutover transitions.
- Create `src/ctl_analysis_registry/lifecycle.py`: seal opportunity generations and resolve Candidate revisions.
- Create `tools/register_chat_analysis.py`: structured Chat registration CLI.
- Create `tools/control_analysis_registry_phase2.py`: shadow/cutover/rollback CLI.
- Create typed payload schemas under `schemas/` for the six new event types.
- Modify `contracts.py`, `events.py`, and `index.py`: schema dispatch and rebuildable projections.
- Modify `setup.py`, `scenario.py`, `abstention.py`, and `scheduler.py`: versioned scoring and scheduling.
- Modify `recorder.py`, `integration.py`, `catchup.py`, and `reporting.py`: end-to-end orchestration.
- Modify `acceptance.py` and `tools/audit_analysis_registry_phase2.py`: enforce Phase 2 acceptance gates.
- Modify the market-analysis skill and repository agent instructions only after runtime behavior is verified.

### Task 1: Extend Typed Events and Rebuildable Projection

**Files:**
- Create: `schemas/prediction_emission_recorded.schema.json`
- Create: `schemas/opportunity_variant_set_frozen.schema.json`
- Create: `schemas/evaluation_job_state_changed.schema.json`
- Create: `schemas/scenario_terminalized.schema.json`
- Create: `schemas/legacy_record_classified.schema.json`
- Create: `schemas/normalization_policy_state_changed.schema.json`
- Modify: `src/ctl_analysis_registry/contracts.py`
- Modify: `src/ctl_analysis_registry/index.py`
- Test: `tests/test_analysis_registry_phase2_event_extensions.py`

**Interfaces:**
- Produces: `validate_phase2_payload(event_type: str, payload: dict[str, Any]) -> list[str]` support for all six new types.
- Produces: projection tables `prediction_emissions`, `opportunity_variant_sets`, `job_state_events`, `legacy_classifications`, and `normalization_policy_states`.
- Produces: aggregate projection for `SCENARIO_TERMINALIZED`.

- [ ] **Step 1: Write failing schema-dispatch and rebuild tests**

```python
NEW_TYPES = {
    "PREDICTION_EMISSION_RECORDED",
    "OPPORTUNITY_VARIANT_SET_FROZEN",
    "EVALUATION_JOB_STATE_CHANGED",
    "SCENARIO_TERMINALIZED",
    "LEGACY_RECORD_CLASSIFIED",
    "NORMALIZATION_POLICY_STATE_CHANGED",
}

def test_new_event_types_are_schema_validated():
    for event_type in NEW_TYPES:
        assert event_type in PHASE2_EVENT_TYPES
        assert validate_phase2_payload(event_type, {}) != []

def test_scenario_terminal_event_projects_outcome_and_all_cancellations(registry):
    append_scenario_terminalized(registry.ledger, scenario_terminal_payload())
    rebuild_index(registry.ledger_path, registry.sqlite_path)
    assert registry.scalar("select count(*) from model_outcomes") == 1
    assert registry.scalar(
        "select count(*) from evaluation_jobs where state='CANCELLED_TERMINAL'"
    ) == 2
```

- [ ] **Step 2: Run tests and verify the new types fail**

Run: `python -m pytest tests/test_analysis_registry_phase2_event_extensions.py -q`

Expected: FAIL because the event types, schemas, and projection handlers do not exist.

- [ ] **Step 3: Add strict schemas and projection handlers**

```python
PHASE2_EVENT_TYPES |= {
    "PREDICTION_EMISSION_RECORDED",
    "OPPORTUNITY_VARIANT_SET_FROZEN",
    "EVALUATION_JOB_STATE_CHANGED",
    "SCENARIO_TERMINALIZED",
    "LEGACY_RECORD_CLASSIFIED",
    "NORMALIZATION_POLICY_STATE_CHANGED",
}

_PAYLOAD_SCHEMAS.update({
    "PREDICTION_EMISSION_RECORDED": "prediction_emission_recorded.schema.json",
    "OPPORTUNITY_VARIANT_SET_FROZEN": "opportunity_variant_set_frozen.schema.json",
    "EVALUATION_JOB_STATE_CHANGED": "evaluation_job_state_changed.schema.json",
    "SCENARIO_TERMINALIZED": "scenario_terminalized.schema.json",
    "LEGACY_RECORD_CLASSIFIED": "legacy_record_classified.schema.json",
    "NORMALIZATION_POLICY_STATE_CHANGED": "normalization_policy_state_changed.schema.json",
})
```

In `_insert_projection`, project `SCENARIO_TERMINALIZED` inside the rebuild transaction by inserting its outcome and updating every listed checkpoint job. Reject missing jobs, duplicate cancellation IDs, or an outcome identity that conflicts with existing payload content.

- [ ] **Step 4: Run focused storage tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_event_extensions.py tests/test_analysis_registry_phase2_storage.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add schemas src/ctl_analysis_registry/contracts.py src/ctl_analysis_registry/index.py tests/test_analysis_registry_phase2_event_extensions.py
git commit -m "feat: add phase two operational events"
```

### Task 2: Add Source-Bound Decision Normalization and Emission Manifests

**Files:**
- Create: `src/ctl_analysis_registry/normalizer.py`
- Modify: `src/ctl_analysis_registry/recorder.py`
- Modify: `schemas/frozen_model_decision.schema.json`
- Test: `tests/test_analysis_registry_phase2_normalizer.py`

**Interfaces:**
- Produces: `Phase2DecisionNormalizer.normalize_zenith(decision_state, snapshot, analysis_id, profile) -> NormalizationResult`.
- Produces: `normalize_chat_envelope(envelope, snapshot, profile) -> NormalizationResult`.
- Produces: `NormalizationResult(decisions, emission_manifest, non_scorable)`.

- [ ] **Step 1: Write failing contract tests**

```python
def test_directional_claims_are_explicit_and_scenarios_are_not_promoted(snapshot):
    state = {"directional_claims": [], "scenarios": [bullish_scenario()]}
    result = Phase2DecisionNormalizer().normalize_zenith(
        state, snapshot, "A-1", "Scalping"
    )
    assert [d for d in result.decisions if d["decision_type"] == "DIRECTIONAL"] == []
    assert result.emission_manifest["families"]["DIRECTIONAL"]["status"] == "ABSTAINED_BY_POLICY"

def test_missing_enabled_family_is_emission_failure(snapshot):
    result = Phase2DecisionNormalizer().normalize_zenith(
        {"scenarios": []}, snapshot, "A-2", "Daytrade"
    )
    assert "EMISSION_MANIFEST_INCOMPLETE" in result.integration_errors
```

- [ ] **Step 2: Run the normalizer tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_normalizer.py -q`

Expected: FAIL with an import error for `ctl_analysis_registry.normalizer`.

- [ ] **Step 3: Implement immutable normalization types and source binding**

```python
@dataclass(frozen=True)
class NormalizationResult:
    decisions: tuple[dict[str, Any], ...]
    emission_manifest: dict[str, Any]
    non_scorable: tuple[dict[str, Any], ...]
    integration_errors: tuple[str, ...]

class Phase2DecisionNormalizer:
    policy_version = "PHASE2_NORMALIZATION_V1"
    emission_policy_version = "DIRECTIONAL_CLAIM_EMISSION_V1"

    def normalize_zenith(
        self,
        decision_state: dict[str, Any],
        snapshot: dict[str, Any],
        analysis_id: str,
        profile: str,
    ) -> NormalizationResult:
        binding = require_native_source_binding(snapshot)
        claims = tuple(decision_state.get("directional_claims", ()))
        return self._normalize_all(decision_state, claims, binding, analysis_id, profile)
```

Require server, symbol specification, broker offset, snapshot/manifest hashes, evidence hashes, freshness/QC, and the last three closed evaluation-timeframe bars. Compute the overlap fingerprint from canonical JSON. Do not use `candidate_id` as a cross-session identity.

- [ ] **Step 4: Add deterministic scenario grammar translation tests and code**

```python
@pytest.mark.parametrize(
    ("runtime_name", "direction", "canonical"),
    [
        ("BREAK_BULLISH", "BULLISH", ["CLOSED_ABOVE"]),
        ("BREAK_BEARISH", "BEARISH", ["CLOSED_BELOW"]),
        ("RETEST_HOLD", "BULLISH", ["ENTERED_BAND", "CLOSED_ABOVE"]),
        ("CONTINUATION", "BEARISH", ["CLOSED_BELOW"]),
    ],
)
def test_scenario_translation(runtime_name, direction, canonical):
    assert translate_scenario_event(event(runtime_name, direction)) == canonical
```

Run: `python -m pytest tests/test_analysis_registry_phase2_normalizer.py -q`

Expected: PASS, including rejection of missing numeric geometry and unsupported events.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/normalizer.py src/ctl_analysis_registry/recorder.py schemas/frozen_model_decision.schema.json tests/test_analysis_registry_phase2_normalizer.py
git commit -m "feat: normalize phase two predictions"
```

### Task 3: Implement Setup Range Scoring V2

**Files:**
- Modify: `src/ctl_analysis_registry/setup.py`
- Modify: `src/ctl_analysis_registry/followup.py`
- Modify: `schemas/followup_evidence.schema.json`
- Test: `tests/test_analysis_registry_phase2_setup_v2.py`

**Interfaces:**
- Produces: `label_setup_v2(decision: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]`.
- Consumes: ordered observations shaped as `{time, bid, ask}`.

- [ ] **Step 1: Write failing BUY, SELL, activation, and gap tests**

```python
def test_buy_enters_only_when_ask_is_inside_range_after_activation():
    result = label_setup_v2(buy_decision(2300, 2302), quotes(
        (1, 2304, 2305), (2, 2300, 2301), activated_at=2
    ))
    assert result["entry_observation_time"] == 2

def test_buy_gap_above_to_below_is_unresolved():
    result = label_setup_v2(
        buy_decision(2300, 2302),
        quotes((1, 2303, 2304), (2, 2298, 2299), activated_at=1),
    )
    assert result["classification"] == "GAP_THROUGH_UNRESOLVED"
```

Add symmetric SELL cases, inclusive-boundary cases, pre-activation movement, and missing bid/ask granularity.

- [ ] **Step 2: Run V2 tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_setup_v2.py -q`

Expected: FAIL because `label_setup_v2` is absent.

- [ ] **Step 3: Implement V2 without changing V1**

```python
def label_setup_v2(decision, evidence):
    lower, upper = decision["entry_range"]
    side = decision["direction"]
    observations = eligible_observations(decision, evidence)
    touch = first_inclusive_touch(observations, side, lower, upper)
    if touch is None and crossed_without_touch(observations, side, lower, upper):
        return setup_outcome(decision, "GAP_THROUGH_UNRESOLVED")
    if touch is None:
        return setup_outcome(decision, "ENTRY_NOT_TRIGGERED")
    return evaluate_tp_sl_after_touch(decision, observations, touch)
```

Dispatch by `labeling_policy_version`; older `SINGLE_TARGET` decisions continue to use `label_setup`.

- [ ] **Step 4: Run V1 and V2 regression tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_setup_v2.py tests/test_analysis_registry_phase2_followup.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/setup.py src/ctl_analysis_registry/followup.py schemas/followup_evidence.schema.json tests/test_analysis_registry_phase2_setup_v2.py
git commit -m "feat: add range-aware setup scoring"
```

### Task 4: Seal Opportunity Generations and Abstention Controls

**Files:**
- Create: `src/ctl_analysis_registry/lifecycle.py`
- Modify: `src/ctl_analysis_registry/abstention.py`
- Modify: `src/ctl_analysis_registry/scheduler.py`
- Test: `tests/test_analysis_registry_phase2_opportunity_lifecycle.py`

**Interfaces:**
- Produces: `opportunity_generation_id(candidate) -> str`.
- Produces: `seal_variant_set(candidates, ledger, now) -> dict[str, Any]`.
- Produces: `build_abstention_control(candidate, disposition) -> dict[str, Any] | None`.

- [ ] **Step 1: Write failing order-independence and revision tests**

```python
def test_variant_reordering_selects_same_representative():
    first = seal_variant_set([early(), full()], memory_ledger(), NOW)
    second = seal_variant_set([full(), early()], memory_ledger(), NOW)
    assert first["representative_decision_id"] == second["representative_decision_id"]

def test_pre_evaluation_revision_supersedes_predecessor():
    state = resolve_revision(old_generation(), revised_generation(), evaluation_started=False)
    assert state.predecessor_state == "SUPERSEDED_PRE_EVALUATION"
    assert state.predecessor_headline_eligible is False
```

- [ ] **Step 2: Run lifecycle tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_opportunity_lifecycle.py -q`

Expected: FAIL because lifecycle functions do not exist.

- [ ] **Step 3: Implement generation identity and sealed selection**

```python
VARIANT_PRIORITY = {
    "FULL_CONFIRMATION": 0,
    "EARLY_CONFIRMATION": 1,
    "CONTINUATION": 2,
}

def opportunity_generation_id(candidate):
    material = {
        key: candidate[key]
        for key in (
            "semantic_opportunity_id", "side", "profile", "timeframe",
            "entry_range", "activation", "stop", "scoring_target",
            "expiry_time", "candidate_policy_version",
        )
    }
    return stable_id("OPPORTUNITY_GENERATION", material)
```

Reject scheduling unless `variant_set_complete is True`. Seal exactly one representative using priority and lexical stable decision ID.

- [ ] **Step 4: Implement pre-outcome abstention control rules**

```python
def build_abstention_control(candidate, disposition):
    if disposition["action"] not in {"WAIT", "REJECT", "WITHHELD"}:
        return None
    if not disposition.get("reason_code"):
        return None
    require_fields(candidate, CONTROL_FIELDS)
    return {
        "source_candidate_decision_id": candidate["decision_id"],
        "abstention_reason": disposition["reason_code"],
        "entry_range": candidate["entry_range"],
        "entry": candidate["scoring_entry"],
        "stop": candidate["stop"],
        "scoring_target": candidate["scoring_target"],
        "trigger": candidate["activation"],
        "expiry_time": candidate["expiry_time"],
    }
```

Run: `python -m pytest tests/test_analysis_registry_phase2_opportunity_lifecycle.py tests/test_analysis_registry_phase2_abstention.py tests/test_candidate_lifecycle.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/lifecycle.py src/ctl_analysis_registry/abstention.py src/ctl_analysis_registry/scheduler.py tests/test_analysis_registry_phase2_opportunity_lifecycle.py
git commit -m "feat: seal opportunity generations"
```

### Task 5: Add Crash-Atomic Scenario Terminalization

**Files:**
- Modify: `src/ctl_analysis_registry/scenario.py`
- Modify: `src/ctl_analysis_registry/catchup.py`
- Test: `tests/test_analysis_registry_phase2_scenario_terminalization.py`

**Interfaces:**
- Produces: `build_scenario_terminal_event(decision, outcome, remaining_jobs, evidence, now) -> dict[str, Any]`.
- Consumes: projection support from Task 1.

- [ ] **Step 1: Write failing crash-replay tests**

```python
def test_one_terminal_event_contains_outcome_and_cancellations():
    event = build_scenario_terminal_event(decision(), outcome(), jobs(), evidence(), NOW)
    assert event["event_type"] == "SCENARIO_TERMINALIZED"
    assert len(event["payload"]["cancelled_checkpoint_jobs"]) == 2

def test_reappend_after_crash_is_idempotent(registry):
    event = terminal_event()
    registry.ledger.append_fsynced(event)
    registry.ledger.append_fsynced(event)
    rebuild_index(registry.ledger_path, registry.sqlite_path)
    assert registry.scalar("select count(*) from model_outcomes") == 1
```

- [ ] **Step 2: Run terminalization tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_scenario_terminalization.py -q`

Expected: FAIL because catch-up still writes evidence and outcome as separate terminal operations.

- [ ] **Step 3: Route Scenario terminal results through one event**

```python
if decision["decision_type"] == "SCENARIO" and is_terminal(outcome):
    event = build_scenario_terminal_event(
        decision, outcome, remaining_checkpoint_jobs, evidence, now
    )
    append_event_idempotently(ledger, event)
else:
    append_followup_and_outcome(ledger, decision, evidence, outcome, now)
```

Checkpoint-only evidence remains `FOLLOWUP_EVIDENCE_RECORDED`. Do not append a separate `MODEL_OUTCOME_RECORDED` for the same terminal operation.

- [ ] **Step 4: Run Scenario and rebuild regression tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_scenario.py tests/test_analysis_registry_phase2_scenario_terminalization.py tests/test_analysis_registry_phase2_storage.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/scenario.py src/ctl_analysis_registry/catchup.py tests/test_analysis_registry_phase2_scenario_terminalization.py
git commit -m "feat: terminalize scenarios atomically"
```

### Task 6: Persist Retry State and Quarantine Legacy Records

**Files:**
- Modify: `src/ctl_analysis_registry/catchup.py`
- Modify: `src/ctl_analysis_registry/backfill.py`
- Modify: `tools/backfill_analysis_registry_phase2.py`
- Test: `tests/test_analysis_registry_phase2_job_state.py`
- Test: `tests/test_analysis_registry_phase2_legacy_classification.py`

**Interfaces:**
- Produces: `job_state_event(job, to_state, reason_code, diagnostic, now, next_retry_time=None)`.
- Produces: `classify_legacy_records(ledger, dry_run: bool) -> dict[str, Any]`.

- [ ] **Step 1: Write failing durability tests**

```python
def test_exception_appends_retry_state_with_sanitized_diagnostic(registry):
    result = run_catchup(adapter=raising_adapter("secret-token"), **registry.args)
    assert result["retried"] == 1
    event = registry.last_event("EVALUATION_JOB_STATE_CHANGED")
    assert event["payload"]["reason_code"] == "FOLLOWUP_COLLECTION_FAILED"
    assert "secret-token" not in event["payload"]["diagnostic"]

def test_legacy_classification_is_idempotent(registry):
    first = classify_legacy_records(registry.ledger, dry_run=False)
    second = classify_legacy_records(registry.ledger, dry_run=False)
    assert first["appended"] > 0
    assert second["appended"] == 0
```

- [ ] **Step 2: Run job-state and legacy tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_job_state.py tests/test_analysis_registry_phase2_legacy_classification.py -q`

Expected: FAIL because exceptions are counted without durable events and legacy classification is not event-sourced.

- [ ] **Step 3: Implement bounded state transitions and classification**

```python
except Exception as exc:
    transition = job_state_event(
        job,
        to_state=next_retry_state(job),
        reason_code=stable_reason_code(exc),
        diagnostic=sanitize_diagnostic(exc),
        now=now,
        next_retry_time=bounded_retry_time(job, now),
    )
    append_event_idempotently(ledger, transition)
```

Classify incomplete legacy decisions as `LEGACY_UNSCORABLE`; classify the known incomplete pending job as `UNRESOLVED_SOURCE_BINDING`. Never infer missing geometry, ATR, price, expiry, or source binding.

- [ ] **Step 4: Run focused catch-up and migration tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_job_state.py tests/test_analysis_registry_phase2_legacy_classification.py tests/test_analysis_registry_phase2_catchup.py tests/test_analysis_registry_phase2_backfill.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/catchup.py src/ctl_analysis_registry/backfill.py tools/backfill_analysis_registry_phase2.py tests/test_analysis_registry_phase2_job_state.py tests/test_analysis_registry_phase2_legacy_classification.py
git commit -m "feat: persist registry retry and legacy state"
```

### Task 7: Add Shadow Cutover, Policy Gate, and Rollback

**Files:**
- Create: `src/ctl_analysis_registry/policy.py`
- Create: `tools/control_analysis_registry_phase2.py`
- Modify: `src/ctl_analysis_registry/ledger.py`
- Modify: `src/ctl_analysis_registry/scheduler.py`
- Modify: `src/ctl_analysis_registry/catchup.py`
- Test: `tests/test_analysis_registry_phase2_policy.py`

**Interfaces:**
- Produces: `active_policy(connection) -> str | None`.
- Produces: `AppendOnlyLedger.head_hash() -> str | None`.
- Produces: `compare_and_set_policy(paths, expected_head, policy_version, state, shadow_summary, now)`.
- Produces: `eligible_due_jobs(connection, now, limit, active_policy_version)`.

- [ ] **Step 1: Write failing stale-head and disabled-policy tests**

```python
def test_cutover_rejects_stale_shadow_source_head(registry):
    append_unrelated_event(registry.ledger)
    with pytest.raises(ShadowBaseStale):
        compare_and_set_policy(
            registry.paths, OLD_HEAD, "PHASE2_NORMALIZATION_V1", "ENABLED",
            shadow_summary(), NOW,
        )

def test_disabled_policy_jobs_are_not_collected(registry):
    disable_policy(registry, "PHASE2_NORMALIZATION_V1")
    result = run_catchup(adapter=spy_adapter(), **registry.args)
    assert result["paused_policy_disabled"] == 1
    assert spy_adapter.calls == []
```

- [ ] **Step 2: Run policy tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_policy.py -q`

Expected: FAIL because policy state and compare-and-append do not exist.

- [ ] **Step 3: Implement policy derivation and lease-protected CAS**

```python
def compare_and_set_policy(paths, expected_head, policy_version, state, shadow_summary, now):
    lease = acquire_registry_writer(
        paths, stable_id("POLICY", policy_version, state), now
    )
    try:
        ledger = AppendOnlyLedger(paths.ledger_path)
        current_head = ledger.head_hash()
        if current_head != expected_head:
            raise ShadowBaseStale("SHADOW_BASE_STALE")
        event = normalization_policy_event(
            policy_version, state, expected_head, shadow_summary, now
        )
        return ledger.append_fsynced(event)
    finally:
        lease.release()
```

Add the read-only ledger helper used by the compare-and-append boundary:

```python
def head_hash(self) -> str | None:
    events = self.read_all()
    return events[-1]["event_hash"] if events else None
```

Derive `PAUSED_POLICY_DISABLED` at query time. Disabled jobs do not collect evidence or consume attempts. Explicit terminalization writes `EVALUATION_JOB_STATE_CHANGED`; re-enable resumes prior durable state.

- [ ] **Step 4: Implement shadow CLI and run policy tests**

The CLI supports `shadow`, `enable`, `disable`, and `terminalize-paused`. `shadow` writes only to an isolated Registry and records both `shadow_source_head` and `shadow_result_head`.

Run: `python -m pytest tests/test_analysis_registry_phase2_policy.py tests/test_analysis_registry_coordination.py tests/test_analysis_registry_paths.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/policy.py src/ctl_analysis_registry/ledger.py src/ctl_analysis_registry/scheduler.py src/ctl_analysis_registry/catchup.py tools/control_analysis_registry_phase2.py tests/test_analysis_registry_phase2_policy.py
git commit -m "feat: govern phase two cutover and rollback"
```

### Task 8: Integrate Normalization with Zenith and Structured Chat

**Files:**
- Modify: `src/ctl_analysis_registry/integration.py`
- Modify: `src/ctl_analysis_registry/chat_model.py`
- Create: `tools/register_chat_analysis.py`
- Modify: `tools/update_market_analysis.py`
- Test: `tests/test_analysis_registry_phase2_registration.py`

**Interfaces:**
- Produces: `register_normalized_analysis(...) -> dict[str, Any]`.
- Produces: CLI exit statuses `RECORDED`, `CHAT_REGISTRATION_BLOCKED`, and `REGISTRY_BLOCKED`.

- [ ] **Step 1: Write failing freeze-before-catch-up tests**

```python
def test_registration_orders_manifest_decisions_jobs_before_catchup(registry):
    result = register_analysis_and_catchup(**registry.native_args())
    types = [event["event_type"] for event in registry.events()]
    assert types.index("PREDICTION_EMISSION_RECORDED") < types.index("DECISION_FROZEN")
    assert types.index("DECISION_FROZEN") < types.index("EVALUATION_JOB_SCHEDULED")
    assert result["registry_recording_status"] == "RECORDED"

def test_chat_cli_blocks_without_structured_envelope(tmp_path):
    result = run_chat_cli(tmp_path, envelope={"narrative": "bullish"})
    assert result["status"] == "CHAT_REGISTRATION_BLOCKED"
```

- [ ] **Step 2: Run registration tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_registration.py -q`

Expected: FAIL because integration still calls legacy freezing directly and the Chat CLI is absent.

- [ ] **Step 3: Route all registration through the normalizer**

```python
normalized = normalizer.normalize_zenith(
    decision_state, snapshot, analysis_id, profile
)
record_emission_manifest(ledger, normalized.emission_manifest)
record_non_scorable(ledger, normalized.non_scorable)
record_frozen_decisions(ledger, normalized.decisions)
schedule_sealed_scorable_decisions(ledger, normalized.decisions)
```

If Registry recording fails, return `REGISTRY_BLOCKED` and do not claim audit continuity. Analysis output may still be displayed. Chat registration accepts only a structured envelope and never parses conversation prose.

- [ ] **Step 4: Run integration, CLI, and launcher tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_registration.py tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_workspace_launcher.py tests/test_analysis_registry_cli_paths.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/integration.py src/ctl_analysis_registry/chat_model.py tools/register_chat_analysis.py tools/update_market_analysis.py tests/test_analysis_registry_phase2_registration.py
git commit -m "feat: register normalized market analysis"
```

### Task 9: Complete Reporting and Acceptance Audit

**Files:**
- Modify: `src/ctl_analysis_registry/reporting.py`
- Modify: `src/ctl_analysis_registry/acceptance.py`
- Modify: `tools/audit_analysis_registry_phase2.py`
- Test: `tests/test_analysis_registry_phase2_reporting_full_loop.py`
- Test: `tests/test_analysis_registry_phase2_acceptance_full_loop.py`

**Interfaces:**
- Produces: reports separated by system, profile, type, headline horizon, regime, volatility, and cohort.
- Produces: acceptance result with explicit gate IDs `P2-01` through `P2-16`.

- [ ] **Step 1: Write failing cohort and generation tests**

```python
def test_reporting_counts_one_variant_per_generation(report_fixture):
    report = build_performance_report(report_fixture.connection)
    assert report["setup"]["headline"]["prediction_count"] == 2
    assert report["setup"]["diagnostic"]["variant_count"] == 4

def test_missing_enabled_family_fails_acceptance(registry):
    result = audit_phase2(registry.paths)
    assert result["gates"]["P2-16"]["status"] == "FAIL"
    assert "EMISSION_MANIFEST_INCOMPLETE" in result["gates"]["P2-16"]["reason_codes"]
```

- [ ] **Step 2: Run reporting and acceptance tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_reporting_full_loop.py tests/test_analysis_registry_phase2_acceptance_full_loop.py -q`

Expected: FAIL because reports do not understand generations, policy state, manifests, or new terminal events.

- [ ] **Step 3: Implement reporting and the sixteen gates**

```python
HEADLINE_HORIZONS = {"Scalping": "PT1H", "Daytrade": "P1D"}

def headline_eligible(row):
    return (
        row["cohort"] == "NATIVE_PHASE2"
        and row["headline_eligible"]
        and row["horizon"] == HEADLINE_HORIZONS[row["profile"]]
    )
```

Deduplicate Setup and Abstention by `opportunity_generation_id`, not by semantic opportunity alone. Keep diagnostic horizons separate. Always report capability, coverage, and efficacy independently; default efficacy remains `INSUFFICIENT_EVIDENCE`.

- [ ] **Step 4: Run all Phase 2 tests**

Run: `python -m pytest tests/test_analysis_registry_phase2_*.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ctl_analysis_registry/reporting.py src/ctl_analysis_registry/acceptance.py tools/audit_analysis_registry_phase2.py tests/test_analysis_registry_phase2_reporting_full_loop.py tests/test_analysis_registry_phase2_acceptance_full_loop.py
git commit -m "feat: audit phase two full-loop coverage"
```

### Task 10: Prove End-to-End Replay, Restart, and Safety

**Files:**
- Create: `tests/fixtures/analysis_registry_phase2/native_live_shaped_snapshot.json`
- Create: `tests/fixtures/analysis_registry_phase2/ordered_bid_ask_followup.json`
- Create: `tests/test_analysis_registry_phase2_full_loop_e2e.py`
- Modify: `tools/run_all_validation.py`

**Interfaces:**
- Consumes all previous tasks.
- Produces a fixture/replay proof for all four decision types and a separate native-forward readiness gate.

- [ ] **Step 1: Add failing full-loop tests**

```python
@pytest.mark.parametrize("decision_type", ["DIRECTIONAL", "SCENARIO", "SETUP", "ABSTENTION"])
def test_fixture_full_loop_survives_projection_deletion(decision_type, registry):
    register_fixture_decision(registry, decision_type)
    run_catchup(**registry.catchup_args())
    expected = registry.outcome_hashes()
    registry.sqlite_path.unlink()
    rebuild_index(registry.ledger_path, registry.sqlite_path)
    assert registry.outcome_hashes() == expected
    assert registry.safety_counters() == {
        "trade_write_enabled": False,
        "auto_execution_enabled": False,
        "order_actions": 0,
        "permission_leakage": 0,
    }
```

- [ ] **Step 2: Run the end-to-end test**

Run: `python -m pytest tests/test_analysis_registry_phase2_full_loop_e2e.py -q`

Expected: FAIL until the fixture adapters and integrated validation entry are wired.

- [ ] **Step 3: Add deterministic fixtures and validation stage**

```python
def validate_phase2_full_loop(output_root: Path) -> dict[str, Any]:
    result = run_fixture_full_loop(output_root / "phase2_full_loop")
    return {
        "status": "PASS" if result["failures"] == 0 else "FAIL",
        "outcomes": result["outcomes"],
        "safety": result["safety"],
    }
```

The fixture is real-shaped but labeled `SYNTHETIC` or `REPLAY`; it must never be represented as native-live evidence.

- [ ] **Step 4: Run focused and full validation**

Run: `python -m pytest tests/test_analysis_registry_phase2_full_loop_e2e.py -q`

Expected: PASS.

Run: `python -m pytest -q`

Expected: PASS with zero failures.

Run: `python tools/run_all_validation.py --output outputs/integrated_validation`

Expected: exit code 0, Phase 2 fixture stage `PASS`, and no claim of validated trading edge.

- [ ] **Step 5: Commit**

```powershell
git add tests/fixtures/analysis_registry_phase2 tests/test_analysis_registry_phase2_full_loop_e2e.py tools/run_all_validation.py
git commit -m "test: prove phase two full-loop rebuild"
```

### Task 11: Align Operator Documentation, Agent Contract, and Skill

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/00_SYSTEM_OVERVIEW.md`
- Modify: `reports/KNOWN_GAPS.md`
- Modify: `skills/ctl-market-analysis-registry/SKILL.md`
- Test: `tests/test_market_analysis_registry_skill.py`
- Test: `tests/test_integrated_repository.py`

**Interfaces:**
- Documents foreground automatic registration, bounded catch-up, manual audit, structured Chat boundary, policy state, and non-live acceptance limits.

- [ ] **Step 1: Write failing documentation-contract tests**

```python
def test_skill_requires_normalized_registration_and_bounded_catchup():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "PHASE2_NORMALIZATION_V1" in text
    assert "bounded foreground catch-up" in text
    assert "REGISTRY_BLOCKED" in text
    assert "no persistent background service" in text
```

- [ ] **Step 2: Run documentation tests**

Run: `python -m pytest tests/test_market_analysis_registry_skill.py tests/test_integrated_repository.py -q`

Expected: FAIL on the new runtime contract assertions.

- [ ] **Step 3: Update documentation without overstating readiness**

Document these exact operational facts:

```text
Normal current-market analysis records a source-bound emission manifest,
decisions, sealed opportunity generations, and jobs before bounded catch-up.
No daemon runs between requests. Disabled policy jobs remain paused.
Fixture acceptance proves measurement mechanics, not predictive edge.
Native Phase 2 remains incomplete until a forward LIVE_MT5 headline outcome
passes the acceptance audit.
```

Keep the known MT5 integrity and forward-shadow gaps until native evidence actually closes them.

- [ ] **Step 4: Run repository contract and full suite**

Run: `python -m pytest tests/test_market_analysis_registry_skill.py tests/test_integrated_repository.py -q`

Expected: PASS.

Run: `python -m pytest -q`

Expected: PASS with zero failures.

- [ ] **Step 5: Commit**

```powershell
git add AGENTS.md docs/00_SYSTEM_OVERVIEW.md reports/KNOWN_GAPS.md skills/ctl-market-analysis-registry/SKILL.md tests/test_market_analysis_registry_skill.py tests/test_integrated_repository.py
git commit -m "docs: align phase two registry operations"
```

### Task 12: Dry-Run Migration and Prepare Native Forward Gate

**Files:**
- Modify: `tools/audit_analysis_registry_phase2.py`
- Create: `docs/runbooks/analysis-registry-phase2-cutover.md`
- Test: `tests/test_analysis_registry_phase2_cutover_runbook.py`

**Interfaces:**
- Produces a repeatable dry-run procedure; it does not enable policy or mutate canonical live history during implementation.

- [ ] **Step 1: Write failing dry-run safety test**

```python
def test_shadow_dry_run_does_not_change_canonical_head(canonical_registry, tmp_path):
    before = canonical_registry.ledger.head_hash()
    result = run_shadow(canonical_registry.paths, tmp_path / "shadow")
    assert canonical_registry.ledger.head_hash() == before
    assert result["shadow_source_head"] == before
    assert result["shadow_result_head"] != before
```

- [ ] **Step 2: Run cutover safety test**

Run: `python -m pytest tests/test_analysis_registry_phase2_cutover_runbook.py -q`

Expected: FAIL until the audit wrapper and runbook contract are present.

- [ ] **Step 3: Add runbook and audit output**

The runbook must require, in order:

```text
1. Resolve the canonical root from runtime/analysis_registry/registry.json.
2. Record canonical head and counts.
3. Copy ledger and immutable evidence to an isolated shadow root.
4. Rebuild, classify legacy records, and execute fixture/replay shadow checks.
5. Compare counts, stable IDs, reason distributions, hashes, parity, and safety.
6. Acquire the writer lease and compare canonical head with shadow_source_head.
7. Abort with SHADOW_BASE_STALE on mismatch.
8. Enable only through NORMALIZATION_POLICY_STATE_CHANGED after operator approval.
9. Complete one native LIVE_MT5 Directional headline outcome.
10. Keep validated_edge=false and promotion_gate_open=false.
```

- [ ] **Step 4: Run final verification without enabling canonical policy**

Run: `python -m pytest -q`

Expected: PASS with zero failures.

Run: `python tools/run_all_validation.py --output outputs/integrated_validation`

Expected: exit code 0.

Run: `python tools/audit_analysis_registry_phase2.py --dry-run`

Expected: reports shadow readiness and native-forward gaps; canonical ledger head remains unchanged.

- [ ] **Step 5: Commit**

```powershell
git add tools/audit_analysis_registry_phase2.py docs/runbooks/analysis-registry-phase2-cutover.md tests/test_analysis_registry_phase2_cutover_runbook.py
git commit -m "docs: add phase two cutover runbook"
```

## Completion Criteria

- Every task has passed its focused tests and review gate.
- `python -m pytest -q` passes with zero failures.
- `python tools/run_all_validation.py --output outputs/integrated_validation` exits 0.
- Shadow dry-run leaves the canonical ledger head unchanged.
- Projection deletion and rebuild reproduce decisions, jobs, state, evidence, and outcomes.
- All four safety counters remain at their locked zero/false values.
- Legacy classifications are append-only and headline-excluded.
- Fixture/replay coverage exists for Directional, Scenario, Setup, and Abstention.
- Native Phase 2 is not declared operationally complete until a genuine forward `LIVE_MT5` Directional headline outcome passes the acceptance audit.
- No result is represented as a validated trading edge.
