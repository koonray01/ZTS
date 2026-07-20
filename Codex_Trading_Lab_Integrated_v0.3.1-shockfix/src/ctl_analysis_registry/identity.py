"""Deterministic identities used by the Analysis Performance Registry."""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> str:
    """Return stable compact JSON suitable for hashing and comparisons."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str | bytes) -> str:
    """Return the full lowercase SHA-256 digest for text or bytes."""

    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    """Build a deterministic, bounded identifier from NUL-separated parts."""

    normalized_prefix = str(prefix).strip().upper().replace("-", "_")
    material = "\0".join(str(part) for part in parts)
    return f"{normalized_prefix}_{sha256_hex(material)[:24].upper()}"
