from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import load_json


@dataclass(frozen=True)
class ReplayCase:
    root: Path
    manifest: dict[str, Any]

    @classmethod
    def load(cls, root: str | Path) -> "ReplayCase":
        root = Path(root)
        manifest = load_json(root / "case.json")
        steps = manifest.get("visible_steps", [])
        if len(steps) > 1:
            ids = [step.get("step_id") for step in steps]
            if len(set(ids)) != len(ids) or any(not value for value in ids):
                raise ValueError("visible_steps must have unique non-empty step_id values")
            times = [step.get("replay_time") for step in steps]
            if any(not value for value in times) or times != sorted(times):
                raise ValueError("visible_steps replay_time must be monotonically ordered")
            stages = [step.get("stage") for step in steps]
            if any(stage not in {"T0", "T1", "T2", "T3"} for stage in stages):
                raise ValueError("multi-step replay requires stages T0/T1/T2/T3")
            if stages[-1] != "T3":
                raise ValueError("multi-step replay must terminate at T3")
        return cls(root=root, manifest=manifest)

    @property
    def case_id(self) -> str:
        return self.manifest["case_id"]

    @property
    def steps(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.manifest["visible_steps"])

    def load_snapshot(self, step: dict[str, Any]) -> dict[str, Any]:
        return load_json(self.root / step["snapshot_path"])

    def load_hidden_outcome(self) -> dict[str, Any]:
        return load_json(self.root / self.manifest["hidden_outcome_path"])

    def load_judge_key(self) -> dict[str, Any]:
        return load_json(self.root / self.manifest["judge_key_path"])

    def can_tune(self) -> bool:
        return not self.manifest["locked_for_tuning"]
