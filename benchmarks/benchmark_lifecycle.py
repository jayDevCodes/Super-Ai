from __future__ import annotations

import argparse
import io
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from core.runtime.container_executor import AppleContainerExecutor, CommandResult
from core.runtime.sandbox import SandboxPlan, SandboxPolicy

IMAGE_DIGEST = "sha256:" + ("a" * 64)


class _Process:
    def __init__(self, runner):
        self.runner = runner
        self._returncode = 0
        self._stdout = io.BytesIO(b"ok\n")
        self._stderr = io.BytesIO(b"")

    @property
    def returncode(self):
        return self._returncode

    def poll(self):
        return self._returncode

    def terminate(self):
        self._returncode = -15

    def kill(self):
        self._returncode = -9

    def wait(self, timeout=None):
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


class _Runner:
    def __init__(self):
        self.labels = {}
        self.process = None

    def run(self, command, *, cwd, environment, timeout_seconds):
        if command[:3] == ("container", "system", "status"):
            return self._json({"status": "running"})
        if command[:2] == ("container", "create"):
            self.labels = {}
            for value in command:
                if value.startswith("com.super-ai.") and "=" in value:
                    key, label = value.split("=", 1)
                    self.labels[key] = label
            return CommandResult(0, b"", b"")
        if command[:3] == ("container", "image", "inspect"):
            return self._json([{
                "configuration": {
                    "name": "alpine:latest",
                    "descriptor": {"digest": IMAGE_DIGEST},
                }
            }])
        if command[:2] == ("container", "inspect"):
            container_id = command[-1]
            return self._json([{
                "configuration": {
                    "id": container_id,
                    "labels": dict(self.labels),
                    "image": {"reference": "alpine:latest", "descriptor": {"digest": IMAGE_DIGEST}},
                    "mounts": [
                        {"source": "/host/capability", "destination": "/capability", "options": ["ro"]},
                        {"source": "/host/output", "destination": "/workspace", "options": []},
                    ],
                    "resources": {"cpus": 1, "memoryInBytes": 512 * 1024 * 1024},
                    "readOnly": True,
                    "capDrop": ["ALL"],
                    "initProcess": {"user": {"id": {"uid": 65532, "gid": 65532}}},
                },
                "status": {"state": "created", "networks": []},
            }])
        if command[:4] == ("container", "stats", "--format", "json"):
            return self._json([{
                "id": command[-1],
                "memoryUsageBytes": 16 * 1024 * 1024,
                "memoryLimitBytes": 512 * 1024 * 1024,
                "cpuUsageUsec": 1_000_000,
                "networkRxBytes": 0, "networkTxBytes": 0,
                "blockReadBytes": 0, "blockWriteBytes": 0, "numProcesses": 1,
            }])
        return CommandResult(0, b"", b"")

    def popen(self, command, *, cwd, environment):
        self.process = _Process(self)
        return self.process

    @staticmethod
    def _json(payload):
        return CommandResult(0, json.dumps(payload).encode(), b"")


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
            "operation": "apple_container_lifecycle_orchestration",
            "iterations": self.iterations,
            "warmup": self.warmup,
            "median_ns": self.median_ns,
            "p95_ns": self.p95_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
        }


def _plan(temp: Path) -> SandboxPlan:
    output = temp / "output"
    output.mkdir(parents=True, exist_ok=True)
    return SandboxPlan(
        backend="apple-container",
        image="alpine:latest",
        command=("container", "run", "--read-only", "--network", "none", "--no-dns", "alpine:latest", "sh", "-c", "echo ok"),
        source_path=temp,
        output_path=output,
        policy=SandboxPolicy(memory_mb=512, cpu_threads=1, timeout_seconds=5),
        execution_ready=True,
        safety_note="benchmark",
    )


def benchmark(*, iterations: int = 200, warmup: int = 20) -> BenchmarkSummary:
    if iterations <= 0 or warmup < 0:
        raise ValueError("iterations must be > 0 and warmup must be >= 0")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="super-ai-lifecycle-bench-") as root:
        temp = Path(root)
        executor = AppleContainerExecutor(
            runner=_Runner(),
            control_timeout_seconds=1,
            create_timeout_seconds=1,
            telemetry_interval_seconds=60,
        )
        for _ in range(warmup):
            handle = executor.launch(_plan(temp), cwd=temp, environment={"PATH": "/usr/bin"})
            handle.cleanup()
        samples: list[int] = []
        for _ in range(iterations):
            started = time.perf_counter_ns()
            handle = executor.launch(_plan(temp), cwd=temp, environment={"PATH": "/usr/bin"})
            handle.cleanup()
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
    parser = argparse.ArgumentParser(description="Benchmark Super-Ai Apple Container lifecycle orchestration")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()
    print(benchmark(iterations=args.iterations, warmup=args.warmup).as_dict())


if __name__ == "__main__":
    main()
