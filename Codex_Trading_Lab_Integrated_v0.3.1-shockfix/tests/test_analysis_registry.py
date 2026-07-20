from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from ctl_analysis_registry.identity import canonical_json, sha256_hex, stable_id


ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _bundle() -> dict:
    return {
        "schema_version": "ANALYSIS_REGISTRY_BUNDLE_V0_1",
        "analysis_id": "ANALYSIS_TEST_001",
        "source_class": "LIVE_MT5",
        "integrity_tier": "VERIFIED",
        "analysis": {"snapshot_id": "SNAP_TEST", "symbol": "XAUUSD"},
        "views": [
            {
                "view_id": "VIEW_TEST",
                "system": "ZENITH",
                "action": "HOLD",
                "model_fingerprint": "MODEL_TEST",
            }
        ],
        "decisions": [
            {
                "decision_id": "DECISION_TEST",
                "decision_type": "SCENARIO",
                "action": "HOLD",
                "scorable": True,
                "horizons": ["1h"],
            }
        ],
        "evidence_refs": ["SNAP_TEST"],
    }


def test_identity_canonical_json_is_sorted_and_compact() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert canonical_json({"text": "ไทย"}) == '{"text":"ไทย"}'


def test_identity_stable_id_and_hash_are_deterministic() -> None:
    assert stable_id("ANALYSIS", "XAUUSD", "T0") == stable_id("ANALYSIS", "XAUUSD", "T0")
    assert stable_id("ANALYSIS", "XAUUSD", "T0") != stable_id("ANALYSIS", "XAUUSD", "T1")
    assert stable_id("ANALYSIS", "XAUUSD", "T0").startswith("ANALYSIS_")
    assert sha256_hex("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_schema_valid_bundle_passes_validation() -> None:
    validate(_bundle(), _schema("analysis_registry_bundle.schema.json"))


def test_bundle_unknown_top_level_field_is_rejected() -> None:
    invalid = _bundle()
    invalid["unexpected"] = True
    with pytest.raises(ValidationError):
        validate(invalid, _schema("analysis_registry_bundle.schema.json"))
