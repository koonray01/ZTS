from __future__ import annotations

from typing import Any

from ctl_decision_core import run_decision_core

from .case import ReplayCase
from .clock import ReplayClock
from .submission import FrozenSubmission
from .visibility import enforce_visible_snapshot


class OutcomeNotRevealed(RuntimeError):
    pass


class ReplayIdentityError(RuntimeError):
    pass


class ReplaySession:
    def __init__(self, case: ReplayCase):
        self.case = case
        self.clock = ReplayClock(case.steps)
        self.current_visible_snapshot: dict[str, Any] | None = None
        self.current_decision_state: dict[str, Any] | None = None
        self.frozen_submission: FrozenSubmission | None = None
        self._revealed_outcome: dict[str, Any] | None = None

    def observe(self) -> dict[str, Any]:
        step = self.clock.current_step
        raw = self.case.load_snapshot(step)
        visible = enforce_visible_snapshot(raw, step["replay_time"])
        decision = run_decision_core(visible)
        self.current_visible_snapshot = visible
        self.current_decision_state = decision
        return {
            "case_id": self.case.case_id,
            "step_id": step["step_id"],
            "replay_time": step["replay_time"],
            "snapshot": visible,
            "market_packet": decision["market_packet"],
            "scenario_packet": decision["scenario_packet"],
            "entry_packet": decision["entry_packet"],
            "hidden_outcome_available": False,
        }

    def advance(self) -> dict[str, Any]:
        self.clock.advance()
        self.frozen_submission = None
        return self.observe()

    def submit(self, submission: dict[str, Any]) -> FrozenSubmission:
        if self.current_decision_state is None:
            raise RuntimeError("Call observe() before submit().")
        if self.frozen_submission is not None:
            raise RuntimeError("A submission is already frozen for this step.")
        current = self.clock.current_step
        expected = {
            "case_id": self.case.case_id,
            "step_id": current["step_id"],
            "snapshot_id": self.current_visible_snapshot["snapshot_id"],
        }
        mismatches = [
            f"{field}: expected {value!r}, got {submission.get(field)!r}"
            for field, value in expected.items()
            if submission.get(field) != value
        ]
        if mismatches:
            raise ReplayIdentityError("Replay submission identity mismatch: " + "; ".join(mismatches))
        self.frozen_submission = FrozenSubmission(submission)
        return self.frozen_submission

    def reveal(self) -> dict[str, Any]:
        if self.frozen_submission is None:
            raise OutcomeNotRevealed("Freeze a submission before revealing outcome.")
        if len(self.case.steps) > 1:
            final_step = self.case.steps[-1]
            current_stage = self.clock.current_step.get("stage", "")
            final_stage = final_step.get("stage", "")
            if self.clock.index != len(self.case.steps) - 1 or final_stage != "T3" or current_stage != "T3":
                raise OutcomeNotRevealed("Outcome is hidden until the final T3 replay stage.")
        self._revealed_outcome = self.case.load_hidden_outcome()
        return dict(self._revealed_outcome)

    @property
    def hidden_outcome(self) -> dict[str, Any]:
        if self._revealed_outcome is None:
            raise OutcomeNotRevealed("Outcome has not been revealed.")
        return dict(self._revealed_outcome)
