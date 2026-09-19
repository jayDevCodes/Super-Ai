from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from core.runtime.container_executor import CommandResult
from core.runtime.preflight import AppleContainerPreflight, ImageIdentity

DIGEST = "sha256:" + ("a" * 64)


class _Runner:
    def run(self, command, *, cwd, environment, timeout_seconds):
        if command[:3] == ("container", "image", "inspect"):
            payload = [{"configuration": {"name": "alpine:latest", "descriptor": {"digest": DIGEST}}}]
            return CommandResult(0, json.dumps(payload).encode(), b"")
        if command[:3] == ("container", "system", "status"):
            return CommandResult(0, b'{"status":"running"}', b"")
        return CommandResult(1, b"", b"unexpected")


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
        return self.__dict__ if False else {
            "operation": self.operation, "iterations": self.iterations, "warmup": self.warmup,
            "median_ns": self.median_ns, "p95_ns": self.p95_ns,
            "min_ns": self.min_ns, "max_ns": self.max_ns,
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
    return BenchmarkSummary(operation, iterations, warmup, statistics.median(ordered), float(ordered[p95_index]), ordered[0], ordered[-1])


def benchmark(*, iterations: int = 20_000, warmup: int = 2_000) -> tuple[BenchmarkSummary, ...]:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be > 0 and warmup must be >= 0")
    runner = _Runner()
    preflight = AppleContainerPreflight(runner, cwd=Path("/tmp"), environment={"PATH": "/usr/bin"}, timeout_seconds=1)
    identity = ImageIdentity(reference="alpine:latest", digest=DIGEST)
    return (
        _sample("image_identity_validation", identity.validate, iterations=iterations, warmup=warmup),
        _sample("image_identity_resolution", lambda: preflight.resolve_image("alpine:latest"), iterations=iterations, warmup=warmup),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Super-Ai image identity validation and resolution")
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--warmup", type=int, default=2_000)
    args = parser.parse_args()
    for summary in benchmark(iterations=args.iterations, warmup=args.warmup):
        print(summary.as_dict())


if __name__ == "__main__":
    main()
