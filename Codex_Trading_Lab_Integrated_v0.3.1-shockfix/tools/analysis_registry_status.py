from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_analysis_registry.catchup import registry_status
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, load_registry_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read Analysis Registry scheduling status.")
    parser.add_argument("--registry-config", type=Path, default=DEFAULT_WORKSPACE_CONFIG)
    parser.add_argument("--registry-root", type=Path)
    args = parser.parse_args(argv)
    paths = load_registry_paths(args.registry_config, registry_root=args.registry_root)
    result = registry_status(paths.sqlite, datetime.now(timezone.utc))
    print(json.dumps({**paths.metadata(), **result}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
