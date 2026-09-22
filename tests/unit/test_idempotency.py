from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from core.runtime.idempotency import (
    IdempotencyClaimError,
    IdempotencyConflictError,
    IdempotencyCoordinator,
    request_fingerprint,
)
from core.runtime.execution import ExecutionResult, ExecutionStatus


def result(stdout: str = "ok") -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        stdout=stdout,
        stderr="",
        duration_seconds=0.01,
        timed_out=False,
        stdout_truncated=False,
        stderr_truncated=False,
        verified=True,
        cleanup_completed=True,
    )


class IdempotencyCoordinatorTests(unittest.TestCase):
    def test_claim_replays_completed_result(self):
        coordinator = IdempotencyCoordinator()
        first = coordinator.claim("request-1", "a" * 64)
        self.assertTrue(first.owner)
        first.complete(result("first"))

        replay = coordinator.claim("request-1", "a" * 64)
        self.assertFalse(replay.owner)
        self.assertIsNotNone(replay.replay)
        self.assertEqual(replay.replay.result.stdout, "first")

    def test_reuse_with_different_fingerprint_conflicts(self):
        coordinator = IdempotencyCoordinator()
        first = coordinator.claim("request-1", "a" * 64)
        with self.assertRaises(IdempotencyConflictError):
            coordinator.claim("request-1", "b" * 64)
        first.abort()

    def test_aborted_claim_can_be_retried(self):
        coordinator = IdempotencyCoordinator()
        first = coordinator.claim("request-1", "a" * 64)
        first.abort()
        second = coordinator.claim("request-1", "b" * 64)
        self.assertTrue(second.owner)
        second.abort()

    def test_claim_without_key_is_independent(self):
        coordinator = IdempotencyCoordinator()
        first = coordinator.claim(None, "a" * 64)
        second = coordinator.claim(None, "a" * 64)
        self.assertTrue(first.owner)
        self.assertTrue(second.owner)

    def test_invalid_key_is_rejected(self):
        coordinator = IdempotencyCoordinator()
        with self.assertRaises(ValueError):
            coordinator.claim("bad" + chr(10) + "key", "a" * 64)

    def test_invalid_fingerprint_is_rejected(self):
        coordinator = IdempotencyCoordinator()
        with self.assertRaises(ValueError):
            coordinator.claim("request-1", "not-a-digest")

    def test_concurrent_claims_deduplicate(self):
        coordinator = IdempotencyCoordinator()
        first = coordinator.claim("request-1", "a" * 64)
        owners = []

        def contender():
            claim = coordinator.claim("request-1", "a" * 64)
            owners.append(claim.owner)

        thread = threading.Thread(target=contender)
        thread.start()
        first.complete(result("one"))
        thread.join(timeout=1)

        self.assertEqual(owners, [False])

    def test_completed_entries_are_bounded(self):
        coordinator = IdempotencyCoordinator(max_entries=1)
        for key in ("one", "two"):
            claim = coordinator.claim(key, "a" * 64)
            claim.complete(result(key))

        self.assertEqual(coordinator.size(), 1)

    def test_large_output_is_bounded_for_replay(self):
        coordinator = IdempotencyCoordinator(replay_output_bytes=4)
        claim = coordinator.claim("request-1", "a" * 64)
        claim.complete(result("123456789"))

        replay = coordinator.claim("request-1", "a" * 64)
        self.assertEqual(replay.replay.result.stdout, "1234")
        self.assertTrue(replay.replay.result.stdout_truncated)

    def test_fingerprint_is_deterministic_and_changes_with_semantics(self):
        common = dict(
            capability_id="demo",
            version="1.0.0",
            image="alpine:3.22",
            command=("true",),
            expected_image_digest=None,
            workspace_root="/tmp/super-ai",
            output_path="/tmp/super-ai/demo/one",
            timeout_seconds=60.0,
            network="disabled",
            output_contract={
                "required_files": [],
                "max_files": 256,
                "max_total_bytes": 64 * 1024 * 1024,
                "max_single_file_bytes": 16 * 1024 * 1024,
                "allow_symlinks": False,
            },
        )
        first = request_fingerprint(**common)
        second = request_fingerprint(**common)
        changed = request_fingerprint(**{**common, "command": ("false",)})
        changed_process = request_fingerprint(
            **{**common, "max_processes": 32}
        )
        changed_files = request_fingerprint(
            **{**common, "max_open_files": 2048}
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, changed)
        self.assertNotEqual(first, changed_process)
        self.assertNotEqual(first, changed_files)


if __name__ == "__main__":
    unittest.main()
