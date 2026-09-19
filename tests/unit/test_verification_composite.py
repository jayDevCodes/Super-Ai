from __future__ import annotations

import unittest

from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.verification import AllOfVerifier, AnyOfVerifier, PredicateVerifier, VerificationError


def result():
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_seconds=0.1,
        timed_out=False,
        stdout_truncated=False,
        stderr_truncated=False,
        verified=None,
        cleanup_completed=True,
        sandbox_attested=True,
    )


class VerificationTests(unittest.TestCase):
    def test_all_of_requires_every_check(self):
        verifier = AllOfVerifier([
            PredicateVerifier(lambda r: True, "a"),
            PredicateVerifier(lambda r: False, "b"),
        ])
        self.assertFalse(verifier.verify(result()))

    def test_any_of_accepts_any_success(self):
        verifier = AnyOfVerifier([
            PredicateVerifier(lambda r: False, "a"),
            PredicateVerifier(lambda r: True, "b"),
        ])
        self.assertTrue(verifier.verify(result()))

    def test_predicate_exception_fails_closed(self):
        def boom(_):
            raise RuntimeError("bad")
        with self.assertRaises(VerificationError):
            PredicateVerifier(boom, "boom").verify(result())


if __name__ == "__main__":
    unittest.main()
