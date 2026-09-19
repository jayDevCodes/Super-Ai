from __future__ import annotations

import unittest

from benchmarks.benchmark_execution_metadata import benchmark
from core.contracts import OutputInspection
from core.runtime.execution import ExecutionResult, ExecutionStatus


class ExecutionMetadataTests(unittest.TestCase):
    def _result(self) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="secret-like output",
            stderr="diagnostic output",
            duration_seconds=0.2,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry={"network_activity_observed": False},
            output_inspection=OutputInspection(
                passed=True,
                file_count=1,
                total_bytes=2,
                missing_required=(),
                violations=(),
            ),
        )

    def test_metadata_projection_is_bounded_and_excludes_payloads(self):
        metadata = self._result().as_metadata()
        self.assertEqual(metadata["status"], "completed")
        self.assertEqual(metadata["exit_code"], 0)
        self.assertEqual(metadata["duration_seconds"], 0.2)
        self.assertNotIn("stdout", metadata)
        self.assertNotIn("stderr", metadata)
        self.assertNotIn("telemetry", metadata)
        self.assertEqual(len(metadata["sandbox_image_digest"]), 71)
        self.assertEqual(metadata["output"]["file_count"], 1)
        self.assertEqual(metadata["output"]["passed"], True)

    def test_benchmark_returns_expected_operations(self):
        results = benchmark(iterations=100, warmup=10)
        self.assertEqual(
            [item.operation for item in results],
            ["execution_result_construction", "execution_metadata_projection"],
        )
        for item in results:
            self.assertEqual(item.iterations, 100)
            self.assertEqual(item.warmup, 10)
            self.assertGreaterEqual(item.median_ns, 0)
            self.assertGreaterEqual(item.p95_ns, item.median_ns)
            self.assertGreaterEqual(item.max_ns, item.min_ns)


if __name__ == "__main__":
    unittest.main()
