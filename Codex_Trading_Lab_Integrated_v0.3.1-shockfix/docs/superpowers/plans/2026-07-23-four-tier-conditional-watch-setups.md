# Four-Tier Conditional Watch Setups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and register sixteen immutable XAUUSD conditional watch setups covering Scalping/Daytrade, four strictness levels, and SELL-continuation/BUY-reversal branches, with activation-gated tracking and no broker writes.

**Architecture:** Add a focused setup-matrix builder that derives deterministic geometry from one fresh market packet and emits a structured `CHAT_MODEL` envelope. Extend the Registry contract and scheduler with `CONDITIONAL_SETUP`, preserve setup geometry through activation, and evaluate outcomes through the existing bid/ask-aware scorer. Expose the workflow through the canonical live-analysis CLI and align Agent/Skill routing with the executable contract.

**Tech Stack:** Python 3.11+, pytest, JSON Schema Draft 2020-12, SQLite, append-only JSONL Registry, PowerShell launcher.

## Global Constraints

- The canonical Registry root is `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`.
- Use one fresh `LIVE_MT5` snapshot and one Registry registration per setup generation.
- Setup matrix size is exactly 16: 2 horizons × 4 strictness variants × 2 directions.
- Strictness values are exactly `EXPLORATORY`, `VERY_RELAXED`, `RELAXED`, and `NORMAL`.
- Minimum frozen reward-to-risk values are 0.50, 0.75, 1.00, and 1.50 respectively.
- All generated setups use `system=CHAT_MODEL`, `decision_type=SETUP`, and `decision_subtype=CONDITIONAL_SETUP`.
- Four strictness variants share one semantic opportunity per horizon/direction/generation and use strictness as `variant_id`.
- Never weaken QC, freshness, shock/block, Candidate, Permission, or broker-safety gates by strictness.
- Keep `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0`.
- No setup, Registry event, or outcome grants trading Permission.

---

### Task 1: Conditional Setup Contract

**Files:**
- Modify: `schemas/frozen_model_decision.schema.json`
- Modify: `src/ctl_analysis_registry/contracts.py`
- Test: `tests/test_analysis_registry_conditional_setup_contract.py`

**Interfaces:**
- Consumes: frozen decision dictionaries produced by `freeze_chat_model_view`.
- Produces: schema-valid `CONDITIONAL_SETUP` decisions with `activation`, `setup_geometry`, `strictness`, `generation_id`, and geometry provenance.

- [ ] **Step 1: Write failing schema tests**

```python
from copy import deepcopy

import pytest
from jsonschema import ValidationError, validate

from ctl_analysis_registry.contracts import load_schema


def conditional_setup() -> dict:
    return {
        "decision_id": "D1", "analysis_id": "A1", "view_id": "V1",
        "system": "CHAT_MODEL", "decision_type": "SETUP",
        "decision_subtype": "CONDITIONAL_SETUP",
        "prediction_family_id": "PF1",
        "semantic_opportunity_id": "OPP_SCALPING_SELL_G1",
        "variant_id": "EXPLORATORY", "symbol": "XAUUSD",
        "direction": "BEARISH", "action": "SETUP", "role": "PRIMARY",
        "decision_time": "2026-07-23T14:00:00Z", "horizons": ["PT30M"],
        "labeling_policy_version": "CONDITIONAL_SINGLE_TARGET_V1",
        "engine_version": "CHAT_SETUP_MATRIX_V1",
        "timeframe_scope": ["M5", "M15"],
        "rules": {"success": "SCORING_TARGET_FIRST", "failure": "STOP_FIRST",
                  "invalidation": {"event_type": "CLOSED_ABOVE", "level": 4058.0},
                  "expiry": "2026-07-23T15:00:00Z"},
        "market_context": {"regime": "TREND", "volatility": "NORMAL"},
        "source_bindings": {"snapshot_id": "S1", "manifest_hash": "a" * 64,
                            "evidence_hashes": ["b" * 64]},
        "quality": {"source_qc": "PASS", "freshness": "FRESH",
                    "integrity_tier": "VERIFIED", "scorable_status": "SCORABLE"},
        "safety": {"trade_write_enabled": False, "auto_execution_enabled": False,
                   "order_actions": 0, "permission_leakage": 0},
        "strictness": "EXPLORATORY", "generation_id": "G1",
        "activation": {
            "condition": {"event_type": "CLOSED_BELOW", "timeframe": "M5",
                          "price_field": "MID_CLOSE", "level": 4050.0},
            "reference_price_method": "ACTIVATION_BAR_CLOSE_MID",
            "atr_config": {"timeframe": "M5", "period": 14, "method": "WILDER"},
            "expiry_time": "2026-07-23T14:30:00Z",
        },
        "setup_geometry": {
            "side": "SELL", "entry": 4050.0, "stop": 4058.0,
            "scoring_target": 4040.0, "expiry_time": "2026-07-23T15:00:00Z",
        },
        "geometry_provenance": {
            "zone_id": "ZONE_M5_SUPPLY_1", "zone_lower": 4050.0,
            "zone_upper": 4056.0, "buffer_method": "SPREAD_PLUS_ATR_FRACTION",
            "policy_version": "FOUR_TIER_GEOMETRY_V1",
        },
    }


def test_conditional_setup_contract_accepts_complete_decision():
    validate(conditional_setup(), load_schema("frozen_model_decision.schema.json"))


@pytest.mark.parametrize("field", ["activation", "setup_geometry", "strictness", "generation_id"])
def test_conditional_setup_contract_rejects_missing_required_field(field):
    payload = deepcopy(conditional_setup())
    payload.pop(field)
    with pytest.raises(ValidationError):
        validate(payload, load_schema("frozen_model_decision.schema.json"))
```

- [ ] **Step 2: Run the contract tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_conditional_setup_contract.py -q`

Expected: FAIL because `CONDITIONAL_SETUP` has no conditional requirements.

- [ ] **Step 3: Extend the schema**

Add a `CONDITIONAL_SETUP` branch to `allOf` requiring:

```json
{
  "if": {
    "properties": {"decision_subtype": {"const": "CONDITIONAL_SETUP"}},
    "required": ["decision_subtype"]
  },
  "then": {
    "required": [
      "activation", "setup_geometry", "strictness",
      "generation_id", "geometry_provenance"
    ]
  }
}
```

Add strictness and setup geometry properties:

```json
"strictness": {
  "enum": ["EXPLORATORY", "VERY_RELAXED", "RELAXED", "NORMAL"]
},
"generation_id": {"type": "string", "minLength": 1},
"setup_geometry": {
  "type": "object",
  "required": ["side", "entry", "stop", "scoring_target", "expiry_time"],
  "properties": {
    "side": {"enum": ["BUY", "SELL"]},
    "entry": {"type": "number"},
    "stop": {"type": "number"},
    "scoring_target": {"type": "number"},
    "expiry_time": {"type": "string", "format": "date-time"}
  },
  "additionalProperties": false
},
"geometry_provenance": {
  "type": "object",
  "required": [
    "zone_id", "zone_lower", "zone_upper",
    "buffer_method", "policy_version"
  ],
  "additionalProperties": true
}
```

- [ ] **Step 4: Run contract tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_conditional_setup_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract**

```powershell
git add schemas/frozen_model_decision.schema.json src/ctl_analysis_registry/contracts.py tests/test_analysis_registry_conditional_setup_contract.py
git commit -m "feat: define conditional setup contract"
```

---

### Task 2: Four-Tier Setup Matrix Builder

**Files:**
- Create: `src/ctl_analysis_registry/setup_matrix.py`
- Test: `tests/test_analysis_registry_setup_matrix.py`

**Interfaces:**
- Consumes: `build_four_tier_setup_envelope(snapshot: dict, decision_state: dict)`.
- Produces: a `CHAT_MODEL` envelope containing exactly sixteen setup claims and `setup_matrix_summary(envelope: dict) -> dict`.

- [ ] **Step 1: Write failing matrix and identity tests**

```python
from ctl_analysis_registry.setup_matrix import (
    build_four_tier_setup_envelope,
    setup_matrix_summary,
)


def test_matrix_contains_sixteen_variants(snapshot, decision_state):
    envelope = build_four_tier_setup_envelope(snapshot, decision_state)
    claims = envelope["claims"]
    assert len(claims) == 16
    assert {c["strictness"] for c in claims} == {
        "EXPLORATORY", "VERY_RELAXED", "RELAXED", "NORMAL"
    }
    assert {c["setup_horizon"] for c in claims} == {"SCALPING", "DAYTRADE"}
    assert {c["side"] for c in claims} == {"BUY", "SELL"}


def test_strictness_variants_share_semantic_opportunity(snapshot, decision_state):
    claims = build_four_tier_setup_envelope(snapshot, decision_state)["claims"]
    scalp_sell = [c for c in claims if c["setup_horizon"] == "SCALPING" and c["side"] == "SELL"]
    assert len({c["semantic_opportunity_id"] for c in scalp_sell}) == 1
    assert len({c["variant_id"] for c in scalp_sell}) == 4


def test_summary_counts_scorable_and_non_scorable(snapshot, decision_state):
    summary = setup_matrix_summary(build_four_tier_setup_envelope(snapshot, decision_state))
    assert summary["variant_count"] == 16
    assert summary["scorable_count"] + summary["non_scorable_count"] == 16
```

- [ ] **Step 2: Run matrix tests and confirm import failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_setup_matrix.py -q`

Expected: FAIL with `ModuleNotFoundError: ctl_analysis_registry.setup_matrix`.

- [ ] **Step 3: Implement constants and envelope skeleton**

```python
STRICTNESS = {
    "EXPLORATORY": {"min_rr": 0.50, "rank": 0},
    "VERY_RELAXED": {"min_rr": 0.75, "rank": 1},
    "RELAXED": {"min_rr": 1.00, "rank": 2},
    "NORMAL": {"min_rr": 1.50, "rank": 3},
}
HORIZONS = {
    "SCALPING": {
        "activation_tf": "M5", "context_tfs": ["M15", "H1"],
        "evaluation_horizon": "PT30M", "activation_bars": 6,
    },
    "DAYTRADE": {
        "activation_tf": "M15", "context_tfs": ["H1", "H4"],
        "evaluation_horizon": "PT2H", "activation_bars": 8,
    },
}
SIDES = {"SELL": "SELL_CONTINUATION", "BUY": "BUY_REVERSAL"}


def build_four_tier_setup_envelope(snapshot: dict, decision_state: dict) -> dict:
    _require_live_safe_snapshot(snapshot)
    generation_id = stable_id("SETUP_GENERATION", snapshot["snapshot_id"], "FOUR_TIER_V1")
    claims = [
        _build_claim(snapshot, decision_state, generation_id, horizon, strictness, side)
        for horizon in HORIZONS
        for strictness in STRICTNESS
        for side in SIDES
    ]
    return {
        "analysis_id": stable_id("ANALYSIS", generation_id, "CHAT_MODEL"),
        "view_id": stable_id("VIEW", generation_id, "CHAT_MODEL"),
        "snapshot_id": snapshot["snapshot_id"],
        "system": "CHAT_MODEL",
        "engine_version": "CHAT_SETUP_MATRIX_V1",
        "generation_id": generation_id,
        "claims": claims,
    }
```

- [ ] **Step 4: Implement deterministic zone selection and geometry**

Implement focused helpers:

```python
def select_zone(active_zones: list[dict], side: str, activation_tf: str, context_tfs: list[str], reference: float) -> dict | None:
    allowed = {"BUY": {"DEMAND", "SUPPORT"}, "SELL": {"SUPPLY", "RESISTANCE"}}[side]
    candidates = [
        z for z in active_zones
        if z.get("zone_type") in allowed and z.get("status", "ACTIVE") == "ACTIVE"
    ]
    timeframe_rank = {activation_tf: 0, **{tf: i + 1 for i, tf in enumerate(context_tfs)}}
    candidates = [z for z in candidates if z.get("timeframe") in timeframe_rank]
    return min(
        candidates,
        key=lambda z: (
            timeframe_rank[z["timeframe"]],
            abs(((float(z["lower_bound"]) + float(z["upper_bound"])) / 2) - reference),
            str(z["zone_id"]),
        ),
        default=None,
    )


def valid_geometry(side: str, entry: float, stop: float, target: float, min_rr: float) -> bool:
    if side == "BUY" and not stop < entry < target:
        return False
    if side == "SELL" and not target < entry < stop:
        return False
    risk = abs(entry - stop)
    return risk > 0 and abs(target - entry) / risk >= min_rr
```

Use the snapshot quote midpoint, selected zone bounds, snapshot spread, and a declared ATR fraction to freeze entry and structural stop. Select the nearest opposing active zone satisfying `min_rr`; otherwise mark the claim non-scorable with `TARGET_OR_RR_UNAVAILABLE`.

- [ ] **Step 5: Add strictness activation grammar tests**

```python
def test_activation_grammar_strengthens_monotonically(snapshot, decision_state):
    claims = build_four_tier_setup_envelope(snapshot, decision_state)["claims"]
    sell = {c["strictness"]: c for c in claims if c["setup_horizon"] == "SCALPING" and c["side"] == "SELL"}
    assert sell["EXPLORATORY"]["activation_policy"]["required_events"] == 1
    assert sell["VERY_RELAXED"]["activation_policy"]["required_events"] == 2
    assert sell["RELAXED"]["activation_policy"]["required_events"] == 3
    assert sell["NORMAL"]["activation_policy"]["required_events"] == 4
```

Represent the executable first activation event in `activation.condition`; preserve the remaining ordered requirements in `activation_policy`. Do not label a claim scorable if the scheduler cannot evaluate every required event.

- [ ] **Step 6: Run matrix tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_setup_matrix.py -q`

Expected: PASS.

- [ ] **Step 7: Commit the matrix builder**

```powershell
git add src/ctl_analysis_registry/setup_matrix.py tests/test_analysis_registry_setup_matrix.py
git commit -m "feat: build four-tier setup matrix"
```

---

### Task 3: Freeze Conditional Setup Provenance

**Files:**
- Modify: `src/ctl_analysis_registry/recorder.py`
- Modify: `src/ctl_analysis_registry/chat_model.py`
- Test: `tests/test_analysis_registry_phase2_recording.py`

**Interfaces:**
- Consumes: setup claims from `build_four_tier_setup_envelope`.
- Produces: immutable frozen decisions retaining activation, strictness, generation, geometry provenance, and activation policy.

- [ ] **Step 1: Add a failing freeze test**

```python
def test_chat_conditional_setup_retains_tracking_contract(snapshot, decision_state):
    envelope = build_four_tier_setup_envelope(snapshot, decision_state)
    frozen = freeze_chat_model_view(envelope, snapshot)
    setup = next(row for row in frozen if row["quality"]["scorable_status"] == "SCORABLE")
    assert setup["decision_subtype"] == "CONDITIONAL_SETUP"
    assert setup["strictness"] in STRICTNESS
    assert setup["generation_id"] == envelope["generation_id"]
    assert setup["activation"]["condition"]["timeframe"] in {"M5", "M15"}
    assert setup["geometry_provenance"]["policy_version"] == "FOUR_TIER_GEOMETRY_V1"
```

- [ ] **Step 2: Run the recording test and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_recording.py::test_chat_conditional_setup_retains_tracking_contract -q`

Expected: FAIL because `_freeze_claim` drops conditional setup metadata.

- [ ] **Step 3: Preserve the conditional setup fields**

In `_freeze_claim`, validate geometry ordering and copy:

```python
if decision_type == "SETUP":
    frozen["setup_geometry"] = {
        key: claim.get(key) for key in
        ("side", "entry", "stop", "scoring_target", "expiry_time")
    }
    if subtype == "CONDITIONAL_SETUP":
        for key in ("activation", "activation_policy", "strictness", "generation_id", "geometry_provenance"):
            frozen[key] = deepcopy(claim[key])
```

Append `INVALID_SIDE_GEOMETRY`, `RR_BELOW_STRICTNESS_FLOOR`, or missing-field reason codes before computing `scorable_status`.

- [ ] **Step 4: Run recording and contract tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_recording.py tests/test_analysis_registry_conditional_setup_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the freezer changes**

```powershell
git add src/ctl_analysis_registry/recorder.py src/ctl_analysis_registry/chat_model.py tests/test_analysis_registry_phase2_recording.py
git commit -m "feat: freeze conditional setup provenance"
```

---

### Task 4: Activation-Gated Setup Scheduling

**Files:**
- Modify: `src/ctl_analysis_registry/scheduler.py`
- Modify: `src/ctl_analysis_registry/integration.py`
- Test: `tests/test_analysis_registry_phase2_scheduler.py`
- Test: `tests/test_analysis_registry_phase2_integration.py`

**Interfaces:**
- Consumes: schema-valid scorable `CONDITIONAL_SETUP` decisions.
- Produces: stable `WAITING_ACTIVATION` jobs and immutable activation events with setup geometry unchanged.

- [ ] **Step 1: Write failing setup-scheduler tests**

```python
def test_conditional_setup_job_waits_for_activation():
    decision = _conditional_setup()
    job = schedule_jobs(decision)[0]
    assert job["state"] == "WAITING_ACTIVATION"
    assert job["evaluation_start"] is None
    assert job["due_at"] == decision["activation"]["expiry_time"]


def test_setup_activation_preserves_geometry():
    decision = _conditional_setup()
    result = activate_conditional(
        decision,
        [_bar(close_time="2026-07-22T10:05:00Z", close=4049.0)],
    )
    assert result["state"] == "ACTIVATED"
    assert result["setup_geometry"] == decision["setup_geometry"]
```

- [ ] **Step 2: Run scheduler tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_scheduler.py -q`

Expected: FAIL because conditional detection only accepts `CONDITIONAL_DIRECTIONAL`.

- [ ] **Step 3: Generalize conditional scheduling**

```python
CONDITIONAL_SUBTYPES = {"CONDITIONAL_DIRECTIONAL", "CONDITIONAL_SETUP"}


def is_conditional(decision: dict[str, Any]) -> bool:
    return decision.get("decision_subtype") in CONDITIONAL_SUBTYPES
```

Use `is_conditional()` in `schedule_jobs`. In `activate_conditional`, copy `setup_geometry`, `strictness`, `generation_id`, and `semantic_opportunity_id` into the activation result for conditional setups without modifying values.

- [ ] **Step 4: Persist activation lifecycle events**

Update integration/catch-up boundaries so a matching closed bar appends exactly one `DECISION_ACTIVATED` event using:

```python
event_id = stable_id(
    "EVENT", "DECISION_ACTIVATED",
    activation["decision_id"], activation["activation_bar_id"],
)
```

Rebuild the index and move the associated job from `WAITING_ACTIVATION` to `PENDING` with activation-based deadlines.

- [ ] **Step 5: Run scheduler and integration tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_phase2_scheduler.py tests/test_analysis_registry_phase2_integration.py -q`

Expected: PASS.

- [ ] **Step 6: Commit activation support**

```powershell
git add src/ctl_analysis_registry/scheduler.py src/ctl_analysis_registry/integration.py tests/test_analysis_registry_phase2_scheduler.py tests/test_analysis_registry_phase2_integration.py
git commit -m "feat: activate conditional setup jobs"
```

---

### Task 5: Conditional Setup Catch-Up and Outcomes

**Files:**
- Modify: `src/ctl_analysis_registry/catchup.py`
- Modify: `src/ctl_analysis_registry/setup.py`
- Modify: `src/ctl_analysis_registry/index.py`
- Test: `tests/test_analysis_registry_conditional_setup_lifecycle.py`

**Interfaces:**
- Consumes: waiting and activated conditional setup jobs plus future bid/ask-aware evidence.
- Produces: terminal activation/outcome events and indexed lifecycle state.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_untriggered_setup_expires_without_outcome(registry, adapter, conditional_setup):
    register(registry, conditional_setup)
    result = run_catchup_for(registry, adapter.with_closed_bar_after_activation_expiry())
    assert result["activation_state"] == "EXPIRED_UNTRIGGERED"
    assert result["model_outcome_count"] == 0


def test_activated_setup_uses_frozen_geometry(registry, adapter, conditional_setup):
    original = dict(conditional_setup["setup_geometry"])
    register(registry, conditional_setup)
    run_catchup_for(registry, adapter.with_activation_then_target())
    outcome = latest_setup_outcome(registry)
    assert outcome["classification"] == "TP_FIRST"
    assert frozen_decision(registry)["setup_geometry"] == original


def test_same_bar_remains_ambiguous_without_refinement(registry, adapter, conditional_setup):
    register(registry, conditional_setup)
    run_catchup_for(registry, adapter.with_activation_then_same_bar_tp_sl())
    assert latest_setup_outcome(registry)["classification"] == "AMBIGUOUS_SAME_BAR"
```

- [ ] **Step 2: Run lifecycle tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_conditional_setup_lifecycle.py -q`

Expected: FAIL because catch-up does not process `WAITING_ACTIVATION` setup jobs.

- [ ] **Step 3: Add activation collection before due-outcome collection**

In `run_catchup`, process bounded `WAITING_ACTIVATION` jobs first:

```python
activation = activate_conditional(decision, adapter.closed_bars(
    symbol=job["symbol"],
    timeframe=decision["activation"]["condition"]["timeframe"],
    start=decision["decision_time"],
    end=decision["activation"]["expiry_time"],
))
```

Append activation/expiry events idempotently. Only activated jobs become eligible for `label_setup`.

- [ ] **Step 4: Keep outcome semantics exact**

Retain existing bid/ask rules:

- BUY enters on ask, exits on bid.
- SELL enters on bid, exits on ask.
- `MID_ONLY_PROXY` is `INVALID_INPUT`.
- Same-bar TP/SL uses M1 and ticks when available; otherwise remains `AMBIGUOUS_SAME_BAR`.
- Expired without entry is `EXPIRED_UNTRIGGERED`.

- [ ] **Step 5: Run lifecycle and existing scorer tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_conditional_setup_lifecycle.py tests/test_analysis_registry_phase2_setup.py tests/test_analysis_registry_phase2_catchup.py -q`

Expected: PASS.

- [ ] **Step 6: Commit lifecycle support**

```powershell
git add src/ctl_analysis_registry/catchup.py src/ctl_analysis_registry/setup.py src/ctl_analysis_registry/index.py tests/test_analysis_registry_conditional_setup_lifecycle.py
git commit -m "feat: track conditional setup outcomes"
```

---

### Task 6: Cohort-Safe Reporting

**Files:**
- Modify: `src/ctl_analysis_registry/reporting.py`
- Modify: `schemas/analysis_performance_report.schema.json`
- Test: `tests/test_analysis_registry_four_tier_reporting.py`

**Interfaces:**
- Consumes: setup outcomes containing horizon, direction, strictness, generation, and semantic opportunity.
- Produces: raw variant diagnostics and deduplicated headline metrics without sample inflation.

- [ ] **Step 1: Write failing cohort tests**

```python
def test_four_strictness_variants_count_as_one_headline_opportunity():
    rows = [
        setup_outcome(opportunity="OPP_1", strictness=value, classification="TP_FIRST")
        for value in ("EXPLORATORY", "VERY_RELAXED", "RELAXED", "NORMAL")
    ]
    report = build_performance_report(connection(rows), {"system": "CHAT_MODEL"})
    assert report["setup"]["raw_variant_count"] == 4
    assert report["setup"]["unique_opportunity_count"] == 1


def test_strictness_cohorts_remain_separate():
    report = build_performance_report(
        connection([
            setup_outcome(opportunity="OPP_1", strictness="EXPLORATORY", classification="TP_FIRST"),
            setup_outcome(opportunity="OPP_1", strictness="NORMAL", classification="SL_FIRST"),
        ]),
        {"system": "CHAT_MODEL"},
    )
    assert report["setup"]["cohorts"]["EXPLORATORY"]["tp_first"] == 1
    assert report["setup"]["cohorts"]["NORMAL"]["sl_first"] == 1
```

- [ ] **Step 2: Run reporting tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_four_tier_reporting.py -q`

Expected: FAIL because strictness cohorts are not emitted.

- [ ] **Step 3: Add explicit cohort keys**

Build setup cohort keys from:

```python
cohort = (
    row["system"], row["setup_horizon"], row["strictness"],
    row["side"], row["market_context"]["regime"],
)
```

Deduplicate headline opportunity count by `(prediction_family_id, semantic_opportunity_id, generation_id)` and retain lexical representative selection only as a deterministic fallback.

- [ ] **Step 4: Run reporting tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_analysis_registry_four_tier_reporting.py tests/test_analysis_registry_phase2_reporting.py -q`

Expected: PASS and existing 30-trigger expectancy gate remains unchanged.

- [ ] **Step 5: Commit reporting**

```powershell
git add src/ctl_analysis_registry/reporting.py schemas/analysis_performance_report.schema.json tests/test_analysis_registry_four_tier_reporting.py
git commit -m "feat: report four-tier setup cohorts"
```

---

### Task 7: Canonical CLI and Runtime Artifact

**Files:**
- Modify: `tools/update_market_analysis.py`
- Modify: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`
- Test: `tests/test_four_tier_setup_cli.py`

**Interfaces:**
- Consumes: CLI flag `--four-tier-setups`.
- Produces: `conditional_setups.json`, one Chat envelope passed to `register_analysis_and_catchup`, and setup status fields in CLI output.

- [ ] **Step 1: Write a failing CLI test**

```python
def test_cli_four_tier_flag_registers_one_envelope(monkeypatch, tmp_path, snapshot, decision_state):
    captured = {}
    monkeypatch.setattr(update_market_analysis, "capture_snapshot", lambda **_: snapshot)
    monkeypatch.setattr(update_market_analysis, "run_decision_core", lambda _: decision_state)
    monkeypatch.setattr(
        update_market_analysis,
        "register_analysis_and_catchup",
        lambda **kwargs: captured.update(kwargs) or {
            "registry_recording_status": "RECORDED", "registered_decision_ids": [],
            "scheduled_jobs": 16, "catchup_status": "COMPLETE",
            "catchup_processed": 0, "catchup_remaining": 16,
            "trade_write_enabled": False, "auto_execution_enabled": False,
            "order_actions": 0, "permission_leakage": 0,
        },
    )
    result = update_market_analysis.main_for_test([
        "--output", str(tmp_path), "--symbol", "XAUUSD",
        "--bars", "120", "--four-tier-setups",
    ])
    assert len(captured["chat_envelope"]["claims"]) == 16
    assert result["setup_class"] == "CONDITIONAL_WATCH_SETUP"
    assert result["setup_variant_count"] == 16
```

- [ ] **Step 2: Run CLI test and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_four_tier_setup_cli.py -q`

Expected: FAIL because the flag and envelope path do not exist.

- [ ] **Step 3: Add the Python CLI flag**

```python
parser.add_argument(
    "--four-tier-setups",
    action="store_true",
    help="Build and register the 16-variant conditional watch setup matrix.",
)
```

When enabled:

```python
chat_envelope = build_four_tier_setup_envelope(snap, decision)
(out / "conditional_setups.json").write_text(
    json.dumps(chat_envelope, indent=2), encoding="utf-8"
)
registry = register_analysis_and_catchup(
    ..., chat_envelope=chat_envelope,
)
```

Emit `setup_class`, `setup_generation_id`, `setup_variant_count`,
`scorable_setup_count`, `non_scorable_setup_count`, `scheduled_jobs`,
Registry/catch-up statuses, and all four safety counters.

- [ ] **Step 4: Add the PowerShell switch**

Add:

```powershell
[switch]$FourTierSetups
```

and append:

```powershell
if ($FourTierSetups) {
    $arguments += "--four-tier-setups"
}
```

- [ ] **Step 5: Run CLI tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_four_tier_setup_cli.py tests/test_analysis_registry_cli_paths.py -q`

Expected: PASS.

- [ ] **Step 6: Commit CLI support**

```powershell
git add tools/update_market_analysis.py tests/test_four_tier_setup_cli.py
git commit -m "feat: expose four-tier setup workflow"
```

- [ ] **Step 7: Deploy the workspace launcher switch**

Patch the existing untracked operational launcher at
`D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`
with the `FourTierSetups` switch from Step 4. This file is outside the
`canonical-main` worktree and must not be staged from that worktree. Verify it
with:

```powershell
& 'D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1' -ResolveOnly
```

Expected: canonical Registry and implementation roots are returned unchanged.

---

### Task 8: Agent and Skill Alignment

**Files:**
- Modify: `AGENTS.md`
- Modify: `skills/ctl-market-analysis-registry/SKILL.md`
- Modify: `skills/ctl-scenario-planner/SKILL.md`
- Modify: `skills/ctl-entry-evaluator/SKILL.md`
- Test: `tests/test_four_tier_setup_skill_contracts.py`

**Interfaces:**
- Consumes: natural-language Scalping, Daytrade, both-horizon, and low-strictness setup requests.
- Produces: one canonical route, one fresh snapshot, one Registry registration, and exact setup/safety reporting requirements.

- [ ] **Step 1: Write failing contract-pressure tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_contract_routes_four_tier_setups_once():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "four-tier" in text.lower()
    assert "CONDITIONAL_WATCH_SETUP" in text
    assert "one fresh snapshot" in text


def test_primary_skill_exposes_required_setup_status_fields():
    text = (ROOT / "skills/ctl-market-analysis-registry/SKILL.md").read_text(encoding="utf-8")
    for token in (
        "setup_generation_id", "setup_variant_count", "scorable_setup_count",
        "scheduled_jobs", "order_actions=0", "permission_leakage=0",
    ):
        assert token in text


def test_supporting_skills_cannot_recapture_or_reregister():
    for relative in (
        "skills/ctl-scenario-planner/SKILL.md",
        "skills/ctl-entry-evaluator/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "do not capture another snapshot" in text.lower()
        assert "do not duplicate Registry writes" in text
```

- [ ] **Step 2: Run pressure tests and confirm failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_four_tier_setup_skill_contracts.py -q`

Expected: FAIL because four-tier lifecycle and response fields are absent.

- [ ] **Step 3: Update Agent and Skills**

Add the exact four-tier matrix, `CONDITIONAL_SETUP` lifecycle, semantic
deduplication, no-retrospective-geometry rule, one-snapshot/one-registration
boundary, and required response fields described in the approved design.
Keep `ctl-market-analysis-registry` as the only primary route; do not add a new
competing skill.

- [ ] **Step 4: Run pressure tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_four_tier_setup_skill_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Agent and Skill changes**

```powershell
git add AGENTS.md skills/ctl-market-analysis-registry/SKILL.md skills/ctl-scenario-planner/SKILL.md skills/ctl-entry-evaluator/SKILL.md tests/test_four_tier_setup_skill_contracts.py
git commit -m "docs: align agents and skills with setup matrix"
```

---

### Task 9: Full Verification and Read-Only Live Acceptance

**Files:**
- Create: `reports/analysis_registry/four_tier_setup_acceptance_20260723.md`
- Test: all files from Tasks 1–8.

**Interfaces:**
- Consumes: completed implementation and connected read-only MT5 terminal.
- Produces: automated verification output plus one live setup generation recorded in the canonical Registry.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest `
  tests/test_analysis_registry_conditional_setup_contract.py `
  tests/test_analysis_registry_setup_matrix.py `
  tests/test_analysis_registry_phase2_recording.py `
  tests/test_analysis_registry_phase2_scheduler.py `
  tests/test_analysis_registry_conditional_setup_lifecycle.py `
  tests/test_analysis_registry_four_tier_reporting.py `
  tests/test_four_tier_setup_cli.py `
  tests/test_four_tier_setup_skill_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the full test suite**

Run: `$env:PYTHONPATH='src'; python -m pytest -q`

Expected: all tests pass with no regression.

- [ ] **Step 3: Run integrated validation**

Run: `python tools/run_all_validation.py --output outputs/integrated_validation_four_tier`

Expected: validation completes successfully and all safety assertions remain zero/false.

- [ ] **Step 4: Run one live read-only setup generation**

From the workspace root:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "runtime\market_analysis\setup_matrix_$stamp"
.\tools\run_zenith_analysis.ps1 -Output $out -Symbol XAUUSD -Bars 120 -FourTierSetups
```

Expected output:

- `source=LIVE_MT5`
- `freshness=FRESH`
- `qc=PASS`
- `setup_class=CONDITIONAL_WATCH_SETUP` or `NO_SETUP` with explicit blocker
- `setup_variant_count=16` when unblocked
- one generation ID
- no more than 16 newly scheduled jobs
- `registry_recording_status=RECORDED`
- `trade_write_enabled=false`
- `auto_execution_enabled=false`
- `order_actions=0`
- `permission_leakage=0`

- [ ] **Step 5: Verify Registry identities and idempotency**

Re-run registration against the same saved snapshot through the test harness and assert no duplicate `DECISION_FROZEN`, `EVALUATION_JOB_SCHEDULED`, or activation events are appended.

- [ ] **Step 6: Write the acceptance report**

Record commands, pass/fail counts, generated setup IDs, scheduled-job count,
Registry/catch-up status, unresolved limitations, and safety counters in:

`reports/analysis_registry/four_tier_setup_acceptance_20260723.md`

- [ ] **Step 7: Commit verification evidence**

```powershell
git add reports/analysis_registry/four_tier_setup_acceptance_20260723.md
git commit -m "test: verify four-tier conditional setups"
```
