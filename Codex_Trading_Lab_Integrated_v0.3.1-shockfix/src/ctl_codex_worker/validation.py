from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import (
    FabricatedPermission,
    InvalidProviderTurn,
    InvalidWorkerResult,
    TokenBudgetExceeded,
)


class ContractValidator:
    def __init__(self, schemas_root: str | Path):
        self.schemas_root = Path(schemas_root)

    def _errors(self, schema_name: str, payload: dict[str, Any]) -> list[str]:
        schema = json.loads(
            (self.schemas_root / schema_name).read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )
        return [
            f"{error.json_path}: {error.message}"
            for error in validator.iter_errors(payload)
        ]

    def provider_turn(self, turn: dict[str, Any]) -> None:
        errors = self._errors("worker_turn.schema.json", turn)
        if errors:
            raise InvalidProviderTurn("; ".join(errors))

    def worker_result(
        self,
        result: dict[str, Any],
        *,
        token_budget: int,
        part3_decisions: list[dict[str, Any]],
    ) -> None:
        errors = self._errors("worker_result.schema.json", result)
        if errors:
            raise InvalidWorkerResult("; ".join(errors))
        if result["usage"]["total_tokens"] > token_budget:
            raise TokenBudgetExceeded(
                f"Result used {result['usage']['total_tokens']} tokens; "
                f"budget is {token_budget}."
            )
        claim = result["permission_claim"]
        if claim == "APPROVED":
            approved = any(
                item.get("decision") == "APPROVED"
                for item in part3_decisions
            )
            if not approved:
                raise FabricatedPermission(
                    "APPROVED permission was claimed without an approved Part 3 tool result."
                )
