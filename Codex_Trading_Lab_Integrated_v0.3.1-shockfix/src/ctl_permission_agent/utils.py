from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sanitize_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    cleaned = cleaned.strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"X_{cleaned}"
    return cleaned[:127]


def evidence_union(*values: Any) -> list[str]:
    refs: list[str] = []

    def collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            if value:
                refs.append(value)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "evidence_refs":
                    collect(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)

    for value in values:
        collect(value)
    return list(dict.fromkeys(refs))


def mask_account(value: str | int | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text)-4)}{text[-2:]}"
