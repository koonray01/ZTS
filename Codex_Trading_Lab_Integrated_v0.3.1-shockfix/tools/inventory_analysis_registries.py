"""Read-only inventory of canonical and legacy Analysis Registries."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def _modified(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def inventory_registries(search_roots: Sequence[Path], canonical_root: Path) -> dict[str, object]:
    canonical = canonical_root.resolve()
    found: dict[Path, dict[str, object]] = {}
    for search_root in search_roots:
        root = Path(search_root).resolve()
        if not root.exists() or not root.is_dir():
            continue
        candidates = [root] if root.name == "analysis_registry" else []
        candidates.extend(path for path in root.rglob("analysis_registry") if path.is_dir())
        for candidate in candidates:
            ledger = candidate / "events.jsonl"
            sqlite = candidate / "index.sqlite"
            if not ledger.exists() and not sqlite.exists() and candidate.resolve() != canonical:
                continue
            resolved = candidate.resolve()
            found[resolved] = {
                "registry_root": str(resolved),
                "canonical": resolved == canonical,
                "ledger_exists": ledger.exists(),
                "ledger_bytes": ledger.stat().st_size if ledger.exists() else 0,
                "sqlite_exists": sqlite.exists(),
                "last_modified": _modified(ledger if ledger.exists() else sqlite),
            }
    return {
        "canonical_root": str(canonical),
        "registries": [found[key] for key in sorted(found, key=lambda item: str(item).casefold())],
        "mutation_performed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, action="append", required=True)
    parser.add_argument("--canonical-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inventory_registries(args.search_root, args.canonical_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
