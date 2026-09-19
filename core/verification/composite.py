from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from core.runtime.execution import ExecutionResult, ExecutionVerifier


class VerificationError(RuntimeError):
    """Raised when composite verification cannot complete safely."""


@dataclass(frozen=True, slots=True)
class VerificationReport:
    passed: bool
    reasons: tuple[str, ...]


class PredicateVerifier:
    """Adapt a bounded predicate into the execution verifier contract."""

    def __init__(self, predicate: Callable[[ExecutionResult], bool], name: str = "predicate"):
        if not name or name.strip() != name:
            raise ValueError("name must be non-empty and trimmed")
        self._predicate = predicate
        self.name = name

    def verify(self, result: ExecutionResult) -> bool:
        try:
            return bool(self._predicate(result))
        except Exception as exc:
            raise VerificationError(
                f"verifier {self.name!r} raised an exception"
            ) from exc


class AllOfVerifier:
    """Pass only when every verifier passes."""

    def __init__(self, verifiers: Sequence[ExecutionVerifier]):
        if not verifiers:
            raise ValueError("verifiers must not be empty")
        self._verifiers = tuple(verifiers)

    def verify(self, result: ExecutionResult) -> bool:
        try:
            for verifier in self._verifiers:
                if not verifier.verify(result):
                    return False
            return True
        except Exception as exc:
            raise VerificationError("composite verification failed closed") from exc


class AnyOfVerifier:
    """Pass when at least one verifier passes, while failing closed on invalid output."""

    def __init__(self, verifiers: Sequence[ExecutionVerifier]):
        if not verifiers:
            raise ValueError("verifiers must not be empty")
        self._verifiers = tuple(verifiers)

    def verify(self, result: ExecutionResult) -> bool:
        try:
            outcomes = [bool(verifier.verify(result)) for verifier in self._verifiers]
        except Exception as exc:
            raise VerificationError("composite verification failed closed") from exc
        return any(outcomes)
