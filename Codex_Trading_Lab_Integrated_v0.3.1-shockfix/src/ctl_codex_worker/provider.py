from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class ModelProvider(Protocol):
    provider_id: str

    def next_turn(
        self,
        *,
        context: dict[str, Any],
        conversation: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ...


@dataclass
class ScriptedProvider:
    turns: list[dict[str, Any]]
    provider_id: str = "SCRIPTED_PROVIDER_V0_1"
    fail_at_call: int | None = None
    retryable_failure: bool = True

    def __post_init__(self) -> None:
        self._index = 0

    def next_turn(
        self,
        *,
        context: dict[str, Any],
        conversation: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._index += 1
        if self.fail_at_call is not None and self._index == self.fail_at_call:
            raise ProviderError(
                "Scripted provider failure.",
                retryable=self.retryable_failure,
            )
        if not self.turns:
            raise ProviderError("Scripted provider has no remaining turn.", retryable=False)
        return self.turns.pop(0)
