"""SQLite access helpers that preserve Registry read/write boundaries."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_readonly_sqlite(sqlite_path: str | Path) -> sqlite3.Connection:
    """Open an existing projection without allowing SQLite to create it."""

    path = Path(sqlite_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Registry index does not exist: {path}")
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
