from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="List replay cases.")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    cases = []
    for manifest_path in sorted(Path(args.root).glob("*/case.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cases.append(
            {
                "case_id": manifest["case_id"],
                "partition": manifest["partition"],
                "difficulty": manifest["difficulty"],
                "tags": manifest["curriculum_tags"],
                "locked_for_tuning": manifest["locked_for_tuning"],
                "path": str(manifest_path.parent),
            }
        )
    print(json.dumps(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
