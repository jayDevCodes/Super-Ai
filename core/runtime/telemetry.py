from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping, Protocol


class _CommandResult(Protocol):
    returncode: int
    stdout: bytes
    stderr: bytes


class TelemetryError(RuntimeError):
    """Raised when a container stats payload cannot be consumed."""


@dataclass(frozen=True, slots=True)
class ContainerStatsSample:
    """One machine-readable Apple Container stats snapshot."""

    timestamp_monotonic: float
    memory_usage_bytes: int | None
    memory_limit_bytes: int | None
    cpu_usage_usec: int | None
    network_rx_bytes: int | None
    network_tx_bytes: int | None
    block_read_bytes: int | None
    block_write_bytes: int | None
    num_processes: int | None


@dataclass(frozen=True, slots=True)
class ContainerTelemetry:
    """Aggregated bounded telemetry retained for one execution."""

    samples: tuple[ContainerStatsSample, ...]
    peak_memory_bytes: int | None
    peak_processes: int | None
    network_rx_bytes: int | None
    network_tx_bytes: int | None
    block_read_bytes: int | None
    block_write_bytes: int | None
    cpu_percent: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": len(self.samples),
            "peak_memory_bytes": self.peak_memory_bytes,
            "peak_processes": self.peak_processes,
            "network_rx_bytes": self.network_rx_bytes,
            "network_tx_bytes": self.network_tx_bytes,
            "block_read_bytes": self.block_read_bytes,
            "block_write_bytes": self.block_write_bytes,
            "cpu_percent": self.cpu_percent,
            "network_activity_observed": (
                self.network_rx_bytes is not None
                and self.network_tx_bytes is not None
                and (self.network_rx_bytes > 0 or self.network_tx_bytes > 0)
            ),
        }


class StatsProvider(Protocol):
    def get_stats(self, container_id: str) -> ContainerStatsSample | None:
        ...


class ContainerStatsCollector:
    """Parse Apple Container stats into a compact execution telemetry record."""

    def __init__(self, provider: StatsProvider) -> None:
        self._provider = provider
        self._samples: list[ContainerStatsSample] = []

    @property
    def samples(self) -> tuple[ContainerStatsSample, ...]:
        return tuple(self._samples)

    def sample(self, container_id: str) -> ContainerStatsSample | None:
        sample = self._provider.get_stats(container_id)
        if sample is not None:
            self._samples.append(sample)
        return sample

    def snapshot(self) -> ContainerTelemetry:
        samples = tuple(self._samples)
        return ContainerTelemetry(
            samples=samples,
            peak_memory_bytes=_max_optional(
                [sample.memory_usage_bytes for sample in samples]
            ),
            peak_processes=_max_optional(
                [sample.num_processes for sample in samples]
            ),
            network_rx_bytes=_last_optional(
                [sample.network_rx_bytes for sample in samples]
            ),
            network_tx_bytes=_last_optional(
                [sample.network_tx_bytes for sample in samples]
            ),
            block_read_bytes=_last_optional(
                [sample.block_read_bytes for sample in samples]
            ),
            block_write_bytes=_last_optional(
                [sample.block_write_bytes for sample in samples]
            ),
            cpu_percent=_cpu_percent(samples),
        )


class AppleContainerStatsProvider:
    """Collect a single JSON stats snapshot with bounded CLI output."""

    def __init__(
        self,
        runner,
        *,
        cwd,
        environment: Mapping[str, str],
        timeout_seconds: float,
    ) -> None:
        self._runner = runner
        self._cwd = cwd
        self._environment = dict(environment)
        self._timeout_seconds = timeout_seconds

    def get_stats(self, container_id: str) -> ContainerStatsSample | None:
        result: _CommandResult = self._runner.run(
            (
                "container",
                "stats",
                "--format",
                "json",
                "--no-stream",
                container_id,
            ),
            cwd=self._cwd,
            environment=self._environment,
            timeout_seconds=self._timeout_seconds,
        )
        if result.returncode != 0:
            return None

        try:
            payload = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelemetryError("container stats output is not valid JSON") from exc

        if isinstance(payload, list):
            if len(payload) != 1:
                raise TelemetryError("container stats must return exactly one sample")
            payload = payload[0]
        if not isinstance(payload, dict):
            raise TelemetryError("container stats sample must be an object")

        return ContainerStatsSample(
            timestamp_monotonic=time.monotonic(),
            memory_usage_bytes=_optional_int(payload, "memoryUsageBytes"),
            memory_limit_bytes=_optional_int(payload, "memoryLimitBytes"),
            cpu_usage_usec=_optional_int(payload, "cpuUsageUsec"),
            network_rx_bytes=_optional_int(payload, "networkRxBytes"),
            network_tx_bytes=_optional_int(payload, "networkTxBytes"),
            block_read_bytes=_optional_int(payload, "blockReadBytes"),
            block_write_bytes=_optional_int(payload, "blockWriteBytes"),
            num_processes=_optional_int(payload, "numProcesses"),
        )


def _optional_int(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TelemetryError(f"stats field {key!r} must be a non-negative integer")
    return value


def _max_optional(values: list[int | None]) -> int | None:
    usable = [value for value in values if value is not None]
    return max(usable) if usable else None


def _last_optional(values: list[int | None]) -> int | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _cpu_percent(samples: tuple[ContainerStatsSample, ...]) -> float | None:
    if len(samples) < 2:
        return None
    first = next((sample for sample in samples if sample.cpu_usage_usec is not None), None)
    last = next(
        (
            sample
            for sample in reversed(samples)
            if sample.cpu_usage_usec is not None
        ),
        None,
    )
    if first is None or last is None or first is last:
        return None
    elapsed_usec = (last.timestamp_monotonic - first.timestamp_monotonic) * 1_000_000
    cpu_delta = last.cpu_usage_usec - first.cpu_usage_usec
    if elapsed_usec <= 0 or cpu_delta < 0:
        return None
    # Apple Container's CPU usage is a cumulative microsecond counter.
    # 100% corresponds to one fully utilized CPU core.
    return (cpu_delta / elapsed_usec) * 100.0
