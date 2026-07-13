from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import SkillMismatch


class SkillLoader:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load(self, skill_id: str, expected_version: str) -> dict[str, Any]:
        folder = self.root / skill_id
        manifest_path = folder / "manifest.json"
        instructions_path = folder / "SKILL.md"
        if not manifest_path.exists() or not instructions_path.exists():
            raise SkillMismatch(f"Skill files are missing: {skill_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["skill_id"] != skill_id:
            raise SkillMismatch("Skill manifest ID mismatch.")
        if manifest["version"] != expected_version:
            raise SkillMismatch(
                f"Skill version mismatch: expected {expected_version}, "
                f"found {manifest['version']}"
            )
        return {
            "manifest": manifest,
            "instructions": instructions_path.read_text(encoding="utf-8"),
        }
