from __future__ import annotations

from dataclasses import dataclass, field
import math
from threading import RLock
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    capability_id: str
    reserved_ram_mb: int
    peak_memory_bytes: int | None
    reserved_cpu_threads: int
    cpu_percent: float | None
    success: bool

    def validate(self) -> None:
        if not self.capability_id or self.capability_id.strip() != self.capability_id:
            raise ValueError("capability_id must be a non-empty trimmed string")
        if self.reserved_ram_mb <= 0:
            raise ValueError("reserved_ram_mb must be > 0")
        if self.reserved_cpu_threads <= 0:
            raise ValueError("reserved_cpu_threads must be > 0")
        if self.peak_memory_bytes is not None and self.peak_memory_bytes < 0:
            raise ValueError("peak_memory_bytes must be >= 0")
        if self.cpu_percent is not None and self.cpu_percent < 0:
            raise ValueError("cpu_percent must be >= 0")


@dataclass(frozen=True, slots=True)
class ResourceRecommendation:
    capability_id: str
    recommended_ram_mb: int
    recommended_parallelism: int
    observations: int
    reason: str


class ResourceFeedbackController:
    """Learn conservative resource recommendations from measured executions."""

    def __init__(
        self,
        *,
        execution_ram_capacity_mb: int,
        cpu_threads: int,
        safety_factor: float = 1.25,
        max_observations_per_capability: int = 20,
    ) -> None:
        if execution_ram_capacity_mb <= 0:
            raise ValueError("execution_ram_capacity_mb must be > 0")
        if cpu_threads <= 0:
            raise ValueError("cpu_threads must be > 0")
        if safety_factor < 1.0:
            raise ValueError("safety_factor must be >= 1")
        if max_observations_per_capability <= 0:
            raise ValueError("max_observations_per_capability must be > 0")
        self._ram_capacity = execution_ram_capacity_mb
        self._cpu_threads = cpu_threads
        self._safety_factor = safety_factor
        self._limit = max_observations_per_capability
        self._observations: dict[str, list[ResourceObservation]] = {}
        self._lock = RLock()

    def record(self, observation: ResourceObservation) -> None:
        observation.validate()
        with self._lock:
            bucket = self._observations.setdefault(observation.capability_id, [])
            bucket.append(observation)
            if len(bucket) > self._limit:
                del bucket[:-self._limit]

    def observations(self, capability_id: str) -> tuple[ResourceObservation, ...]:
        with self._lock:
            return tuple(self._observations.get(capability_id, ()))

    def recommend(
        self,
        capability_id: str,
        *,
        declared_ram_mb: int,
        declared_cpu_threads: int,
        max_parallelism: int,
    ) -> ResourceRecommendation:
        if declared_ram_mb <= 0 or declared_cpu_threads <= 0:
            raise ValueError("declared resources must be > 0")
        if max_parallelism <= 0:
            raise ValueError("max_parallelism must be > 0")

        samples = self.observations(capability_id)
        if not samples:
            return ResourceRecommendation(
                capability_id=capability_id,
                recommended_ram_mb=declared_ram_mb,
                recommended_parallelism=1,
                observations=0,
                reason="no telemetry history; keep conservative declared budget",
            )

        peak_bytes = [
            sample.peak_memory_bytes
            for sample in samples
            if sample.peak_memory_bytes is not None
        ]
        measured_peak_mb = max(
            declared_ram_mb,
            math.ceil(max(peak_bytes, default=declared_ram_mb * 1024 * 1024)
                      / (1024 * 1024) * self._safety_factor),
        )

        recent_cpu = [
            sample.cpu_percent / 100.0
            for sample in samples[-5:]
            if sample.cpu_percent is not None
        ]
        observed_cpu_cores = max(recent_cpu, default=float(declared_cpu_threads))
        cpu_slots = max(1, math.floor(self._cpu_threads / max(observed_cpu_cores, 1.0)))

        ram_slots = max(1, self._ram_capacity // measured_peak_mb)
        parallelism = min(max_parallelism, ram_slots, cpu_slots)

        reason = (
            f"peak_ram={measured_peak_mb}MB, observed_cpu_cores={observed_cpu_cores:.2f}; "
            f"parallelism limited by RAM/CPU capacity"
        )
        return ResourceRecommendation(
            capability_id=capability_id,
            recommended_ram_mb=measured_peak_mb,
            recommended_parallelism=parallelism,
            observations=len(samples),
            reason=reason,
        )

    def record_execution_telemetry(
        self,
        capability_id: str,
        *,
        reserved_ram_mb: int,
        reserved_cpu_threads: int,
        telemetry: dict[str, object] | None,
        success: bool,
    ) -> None:
        telemetry = telemetry or {}
        peak = telemetry.get("peak_memory_bytes")
        cpu = telemetry.get("cpu_percent")
        self.record(
            ResourceObservation(
                capability_id=capability_id,
                reserved_ram_mb=reserved_ram_mb,
                peak_memory_bytes=peak if isinstance(peak, int) else None,
                reserved_cpu_threads=reserved_cpu_threads,
                cpu_percent=cpu if isinstance(cpu, (int, float)) else None,
                success=success,
            )
        )
