from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass

from core.runtime.ownership import OwnershipClaim, new_ownership_claim, verify_container_ownership


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
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return BenchmarkSummary(
        operation=operation,
        iterations=iterations,
        warmup=warmup,
        median_ns=statistics.median(ordered),
        p95_ns=float(ordered[p95_index]),
        min_ns=ordered[0],
        max_ns=ordered[-1],
    )


def benchmark(*, iterations: int = 20_000, warmup: int = 2_000) -> tuple[BenchmarkSummary, ...]:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be > 0 and warmup must be >= 0")

    claim = OwnershipClaim(
        execution_id="a" * 32,
        container_id="super-ai-" + ("a" * 24),
    )
    payload = json.dumps([
        {"configuration": {"id": claim.container_id, "labels": dict(claim.labels)}}
    ])

    return (
        _sample(
            "ownership_claim_creation",
            new_ownership_claim,
            iterations=iterations,
            warmup=warmup,
        ),
        _sample(
            "ownership_verification_from_json",
            lambda: verify_container_ownership(payload, claim),
            iterations=iterations,
            warmup=warmup,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Super-Ai ownership primitives")
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--warmup", type=int, default=2_000)
    args = parser.parse_args()
    for summary in benchmark(iterations=args.iterations, warmup=args.warmup):
        print(summary.as_dict())


if __name__ == "__main__":
    main()
