from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from core.runtime.execution import ExecutionResult, ExecutionStatus


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    operation: str
    iterations: int
    warmup: int
    median_ns: float
    p95_ns: float
    min_ns: int
    max_ns: int

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "iterations": self.iterations,
            "warmup": self.warmup,
            "median_ns": self.median_ns,
            "p95_ns": self.p95_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
        }


def _sample(operation: str, fn, *, iterations: int, warmup: int) -> BenchmarkSummary:
    for _ in range(warmup):
        fn()
    samples: list[int] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - started)
    ordered = sorted(samples)
    return BenchmarkSummary(
        operation=operation,
        iterations=iterations,
        warmup=warmup,
        median_ns=statistics.median(ordered),
        p95_ns=float(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]),
        min_ns=ordered[0],
        max_ns=ordered[-1],
    )


def benchmark(*, iterations: int = 20_000, warmup: int = 2_000) -> tuple[BenchmarkSummary, ...]:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be > 0 and warmup must be >= 0")

    result = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="ignored",
        stderr="ignored",
        duration_seconds=0.01,
        timed_out=False,
        stdout_truncated=False,
        stderr_truncated=False,
        verified=True,
        cleanup_completed=True,
        sandbox_attested=True,
        sandbox_image_digest="sha256:" + "a" * 64,
        telemetry={"network_activity_observed": False},
    )

    return (
        _sample(
            "execution_result_construction",
            lambda: ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                exit_code=0,
                stdout="ignored",
                stderr="ignored",
                duration_seconds=0.01,
                timed_out=False,
                stdout_truncated=False,
                stderr_truncated=False,
                verified=True,
                cleanup_completed=True,
            ),
            iterations=iterations,
            warmup=warmup,
        ),
        _sample(
            "execution_metadata_projection",
            result.as_metadata,
            iterations=iterations,
            warmup=warmup,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Super-Ai execution metadata overhead")
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--warmup", type=int, default=2_000)
    args = parser.parse_args()
    for summary in benchmark(iterations=args.iterations, warmup=args.warmup):
        print(summary.as_dict())


if __name__ == "__main__":
    main()
