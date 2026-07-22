"""Shared writer coordination for every canonical Registry mutator."""

from __future__ import annotations

from datetime import datetime

from .lease import RegistryWriterLease
from .paths import RegistryPaths


def acquire_registry_writer(
    paths: RegistryPaths,
    owner_id: str,
    now: datetime,
    ttl_seconds: int = 60,
) -> RegistryWriterLease:
    return RegistryWriterLease.acquire(
        paths.lease,
        owner_id,
        ttl_seconds,
        now=now,
        operation_log=paths.operations,
    )
