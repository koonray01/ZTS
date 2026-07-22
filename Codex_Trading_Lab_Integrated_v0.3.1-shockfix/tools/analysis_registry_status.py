from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ctl_analysis_registry.catchup import registry_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Analysis Registry scheduling status.")
    parser.add_argument("--sqlite", type=Path, required=True)
    args = parser.parse_args()
    result = registry_status(args.sqlite, datetime.now(timezone.utc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
