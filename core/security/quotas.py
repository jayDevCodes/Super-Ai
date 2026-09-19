from __future__ import annotations

from dataclasses import dataclass


class QuotaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceQuota:
    memory_mb: int
    cpu_threads: int
    disk_mb: int
    processes: int

    def validate(self) -> None:
        for name in ("memory_mb", "cpu_threads", "disk_mb", "processes"):
            if getattr(self, name) <= 0:
                raise QuotaError(f"{name} must be > 0")


class QuotaLedger:
    def __init__(self, total: ResourceQuota) -> None:
        total.validate()
        self._total = total
        self._used = ResourceQuota(0, 0, 0, 0)

    @property
    def available(self) -> ResourceQuota:
        return ResourceQuota(
            self._total.memory_mb - self._used.memory_mb,
            self._total.cpu_threads - self._used.cpu_threads,
            self._total.disk_mb - self._used.disk_mb,
            self._total.processes - self._used.processes,
        )

    def reserve(self, requested: ResourceQuota) -> None:
        requested.validate()
        available = self.available
        if any(
            getattr(requested, field) > getattr(available, field)
            for field in ("memory_mb", "cpu_threads", "disk_mb", "processes")
        ):
            raise QuotaError("requested quota exceeds available capacity")
        self._used = ResourceQuota(
            self._used.memory_mb + requested.memory_mb,
            self._used.cpu_threads + requested.cpu_threads,
            self._used.disk_mb + requested.disk_mb,
            self._used.processes + requested.processes,
        )

    def release(self, requested: ResourceQuota) -> None:
        requested.validate()
        next_used = ResourceQuota(
            self._used.memory_mb - requested.memory_mb,
            self._used.cpu_threads - requested.cpu_threads,
            self._used.disk_mb - requested.disk_mb,
            self._used.processes - requested.processes,
        )
        if min(next_used.memory_mb, next_used.cpu_threads, next_used.disk_mb, next_used.processes) < 0:
            raise QuotaError("release exceeds current reservations")
        self._used = next_used
