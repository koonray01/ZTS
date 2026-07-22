"""Append-only analysis audit registry primitives."""

from .identity import canonical_json, sha256_hex, stable_id
from .contracts import PHASE2_EVENT_TYPES, V2_SCHEMA_VERSION, validate_phase2_payload
from .events import build_event, build_v2_event, event_hash, validate_event_chain
from .ledger import AppendOnlyLedger, LedgerCollisionError, LedgerError
from .recorder import record_zenith_output
from .index import rebuild_index
from .verify import verify_registry

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
    "rebuild_index",
    "verify_registry",
    "validate_event_chain",
    "validate_phase2_payload",
    "PHASE2_EVENT_TYPES",
    "V2_SCHEMA_VERSION",
]
