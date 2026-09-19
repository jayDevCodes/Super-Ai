from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from registry.runtime import RuntimeSpec


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    iterations: int
    warmup: int
    median_ns: float
    p95_ns: float
    min_ns: int
    max_ns: int

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": "runtime_spec_validate",
            "iterations": self.iterations,
            "warmup": self.warmup,
            "median_ns": self.median_ns,
            "p95_ns": self.p95_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
        }


def benchmark(*, iterations: int = 20_000, warmup: int = 2_000) -> BenchmarkSummary:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be > 0 and warmup must be >= 0")
    spec = RuntimeSpec(
        image="alpine:3.22",
        command=("/bin/sh", "-c", "echo ok"),
        timeout_seconds=60.0,
        expected_image_digest="sha256:" + "a" * 64,
        working_directory="/workspace",
    )
    for _ in range(warmup):
        spec.validate()
    samples: list[int] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        spec.validate()
        samples.append(time.perf_counter_ns() - started)
    ordered = sorted(samples)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return BenchmarkSummary(
        iterations=iterations,
        warmup=warmup,
        median_ns=statistics.median(ordered),
        p95_ns=float(ordered[p95_index]),
        min_ns=ordered[0],
        max_ns=ordered[-1],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Super-Ai RuntimeSpec validation")
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--warmup", type=int, default=2_000)
    args = parser.parse_args()
    print(benchmark(iterations=args.iterations, warmup=args.warmup).as_dict())


if __name__ == "__main__":
    main()
