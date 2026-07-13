from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


class FixtureSequenceProvider:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def snapshots(self) -> Iterator[dict]:
        for path in sorted(self.directory.glob("*.json")):
            yield json.loads(path.read_text(encoding="utf-8"))
