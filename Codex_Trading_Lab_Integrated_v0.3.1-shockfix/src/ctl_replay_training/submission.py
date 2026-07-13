from __future__ import annotations

import copy
from typing import Any

from .utils import sha256_json


class SubmissionFrozenError(RuntimeError):
    pass


class FrozenSubmission:
    def __init__(self, submission: dict[str, Any]):
        self._submission = copy.deepcopy(submission)
        self._hash = sha256_json(self._submission)
        self._frozen = True

    @property
    def value(self) -> dict[str, Any]:
        return copy.deepcopy(self._submission)

    @property
    def submission_hash(self) -> str:
        return self._hash

    def replace(self, *_args, **_kwargs) -> None:
        raise SubmissionFrozenError("Submission is frozen and cannot be changed.")
