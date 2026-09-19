from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
import time
from typing import Callable, Iterable

from core.runtime.execution import ExecutionResult, ExecutionStatus


class FailureClass(str, Enum):
    TRANSIENT = "transient"
    RESOURCE = "resource"
    VERIFICATION = "verification"
    SECURITY = "security"
    PERMANENT = "permanent"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.1
    max_backoff_seconds: float = 5.0
    jitter: bool = True

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_backoff_seconds < 0:
            raise ValueError("initial_backoff_seconds must be >= 0")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError(
                "max_backoff_seconds must be >= initial_backoff_seconds"
            )


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retry: bool
    attempt: int
    delay_seconds: float
    reason: str


class RetryController:
    """Bounded retry decisions with idempotence and exponential backoff."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        self._policy = policy or RetryPolicy()
        self._policy.validate()
        self._sleep = sleep
        self._random = random_fn

    def classify(self, result: ExecutionResult) -> FailureClass:
        if result.sandbox_attested is False:
            return FailureClass.SECURITY
        if result.status is ExecutionStatus.VERIFICATION_FAILED:
            return FailureClass.VERIFICATION
        if result.status is ExecutionStatus.TIMED_OUT:
            return FailureClass.RESOURCE
        if result.status is ExecutionStatus.FAILED:
            return FailureClass.TRANSIENT
        return FailureClass.PERMANENT

    def decide(
        self,
        *,
        result: ExecutionResult,
        attempt: int,
        idempotent: bool,
    ) -> RetryDecision:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        if attempt >= self._policy.max_attempts:
            return RetryDecision(False, attempt, 0.0, "retry attempt budget exhausted")
        if not idempotent:
            return RetryDecision(False, attempt, 0.0, "operation is not idempotent")

        failure = self.classify(result)
        if failure is not FailureClass.TRANSIENT:
            return RetryDecision(
                False,
                attempt,
                0.0,
                f"failure class {failure.value} is not retryable",
            )

        ceiling = min(
            self._policy.max_backoff_seconds,
            self._policy.initial_backoff_seconds * (2 ** (attempt - 1)),
        )
        delay = self._random() * ceiling if self._policy.jitter else ceiling
        return RetryDecision(
            True,
            attempt,
            delay,
            "transient failure within retry budget",
        )

    def wait(self, decision: RetryDecision) -> None:
        if decision.retry and decision.delay_seconds > 0:
            self._sleep(decision.delay_seconds)
