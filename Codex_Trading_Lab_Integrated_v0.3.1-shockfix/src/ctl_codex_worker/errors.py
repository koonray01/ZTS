class WorkerError(RuntimeError):
    retryable = False
    code = "WORKER_ERROR"


class RetryableWorkerError(WorkerError):
    retryable = True
    code = "RETRYABLE_WORKER_ERROR"


class PermanentWorkerError(WorkerError):
    retryable = False
    code = "PERMANENT_WORKER_ERROR"


class SkillMismatch(PermanentWorkerError):
    code = "SKILL_MISMATCH"


class DisallowedTool(PermanentWorkerError):
    code = "DISALLOWED_TOOL"


class ToolBudgetExceeded(PermanentWorkerError):
    code = "TOOL_BUDGET_EXCEEDED"


class ToolLoopDetected(PermanentWorkerError):
    code = "TOOL_LOOP_DETECTED"


class TokenBudgetExceeded(PermanentWorkerError):
    code = "TOKEN_BUDGET_EXCEEDED"


class InvalidProviderTurn(PermanentWorkerError):
    code = "INVALID_PROVIDER_TURN"


class InvalidWorkerResult(PermanentWorkerError):
    code = "INVALID_WORKER_RESULT"


class FabricatedPermission(PermanentWorkerError):
    code = "FABRICATED_PERMISSION"


class StateUnavailable(RetryableWorkerError):
    code = "STATE_UNAVAILABLE"
