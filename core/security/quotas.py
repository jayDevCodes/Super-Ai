from __future__ import annotations

from dataclasses import dataclass
import secrets
from threading import RLock


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


@dataclass(frozen=True, slots=True)
class QuotaReservation:
    """Opaque, single-use proof of one quota reservation."""

    reservation_id: str
    quota: ResourceQuota

    def validate(self) -> None:
        if not self.reservation_id or self.reservation_id.strip() != self.reservation_id:
            raise QuotaError("reservation_id must be a non-empty trimmed string")
        self.quota.validate()


class QuotaLedger:
    def __init__(self, total: ResourceQuota) -> None:
        total.validate()
        self._total = total
        self._used = ResourceQuota(0, 0, 0, 0)
        self._reservations: dict[str, ResourceQuota] = {}
        self._lock = RLock()

    @property
    def available(self) -> ResourceQuota:
        with self._lock:
            return ResourceQuota(
                self._total.memory_mb - self._used.memory_mb,
                self._total.cpu_threads - self._used.cpu_threads,
                self._total.disk_mb - self._used.disk_mb,
                self._total.processes - self._used.processes,
            )

    @property
    def used(self) -> ResourceQuota:
        with self._lock:
            return self._used

    def reserve(self, requested: ResourceQuota) -> None:
        self.reserve_lease(requested)

    def reserve_lease(self, requested: ResourceQuota) -> QuotaReservation:
        requested.validate()
        with self._lock:
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
            reservation_id = secrets.token_urlsafe(18)
            self._reservations[reservation_id] = requested
            return QuotaReservation(reservation_id=reservation_id, quota=requested)

    def release(self, requested: ResourceQuota) -> None:
        requested.validate()
        with self._lock:
            self._release(requested)

    def release_lease(self, reservation: QuotaReservation) -> None:
        reservation.validate()
        with self._lock:
            requested = self._reservations.pop(reservation.reservation_id, None)
            if requested is None:
                raise QuotaError("reservation is unknown or already released")
            if requested != reservation.quota:
                self._reservations[reservation.reservation_id] = requested
                raise QuotaError("reservation quota does not match recorded reservation")
            self._release(requested)

    def _release(self, requested: ResourceQuota) -> None:
        next_used = ResourceQuota(
            self._used.memory_mb - requested.memory_mb,
            self._used.cpu_threads - requested.cpu_threads,
            self._used.disk_mb - requested.disk_mb,
            self._used.processes - requested.processes,
        )
        if min(next_used.memory_mb, next_used.cpu_threads, next_used.disk_mb, next_used.processes) < 0:
            raise QuotaError("release exceeds current reservations")
        self._used = next_used
