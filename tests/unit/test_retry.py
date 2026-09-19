from __future__ import annotations

import unittest

from core.recovery import FailureClass, RetryController, RetryPolicy
from core.runtime.execution import ExecutionResult, ExecutionStatus


def result(status):
    return ExecutionResult(
        status=status,
        exit_code=1,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        timed_out=status is ExecutionStatus.TIMED_OUT,
        stdout_truncated=False,
        stderr_truncated=False,
        verified=None,
        cleanup_completed=True,
        sandbox_attested=True,
    )


class RetryTests(unittest.TestCase):
    def test_transient_failure_retries_with_full_jitter(self):
        controller = RetryController(
            RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=1,
                max_backoff_seconds=4,
                jitter=True,
            ),
            random_fn=lambda: 0.5,
        )
        decision = controller.decide(
            result=result(ExecutionStatus.FAILED),
            attempt=1,
            idempotent=True,
        )
        self.assertTrue(decision.retry)
        self.assertEqual(decision.delay_seconds, 0.5)
        self.assertEqual(controller.classify(result(ExecutionStatus.FAILED)), FailureClass.TRANSIENT)

    def test_non_idempotent_operation_is_never_retried(self):
        controller = RetryController()
        decision = controller.decide(
            result=result(ExecutionStatus.FAILED),
            attempt=1,
            idempotent=False,
        )
        self.assertFalse(decision.retry)

    def test_security_and_verification_failures_are_not_retried(self):
        controller = RetryController()
        for status in (
            ExecutionStatus.VERIFICATION_FAILED,
            ExecutionStatus.CLEANUP_FAILED,
        ):
            decision = controller.decide(
                result=result(status),
                attempt=1,
                idempotent=True,
            )
            self.assertFalse(decision.retry)

    def test_attempt_budget_is_bounded(self):
        controller = RetryController(RetryPolicy(max_attempts=2))
        decision = controller.decide(
            result=result(ExecutionStatus.FAILED),
            attempt=2,
            idempotent=True,
        )
        self.assertFalse(decision.retry)


if __name__ == "__main__":
    unittest.main()
