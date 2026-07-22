"""Append-only analysis audit registry primitives."""

from .identity import canonical_json, sha256_hex, stable_id
from .contracts import PHASE2_EVENT_TYPES, V2_SCHEMA_VERSION, validate_phase2_payload
from .events import build_event, build_v2_event, event_hash, validate_event_chain
from .ledger import AppendOnlyLedger, LedgerCollisionError, LedgerError
from .chat_model import freeze_chat_model_view
from .recorder import (
    freeze_zenith_decisions,
    record_frozen_decisions,
    record_zenith_output,
    revise_decision,
)
from .index import rebuild_index
from .verify import verify_registry
from .catchup import registry_status, run_catchup

__all__ = [
    "AppendOnlyLedger",
    "LedgerCollisionError",
    "LedgerError",
    "build_event",
    "build_v2_event",
    "canonical_json",
    "event_hash",
    "sha256_hex",
    "stable_id",
    "record_zenith_output",
    "freeze_zenith_decisions",
    "freeze_chat_model_view",
    "record_frozen_decisions",
    "revise_decision",
    "rebuild_index",
    "verify_registry",
    "run_catchup",
    "registry_status",
    "validate_event_chain",
    "validate_phase2_payload",
    "PHASE2_EVENT_TYPES",
    "V2_SCHEMA_VERSION",
]
