from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .resources import ResourceContract, TaskConstraints


class ResourceLimitError(RuntimeError):
    """Raised when admitting a worker would violate the resource budget."""


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Observed host state used by the deterministic admission controller."""

    total_ram_mb: int
    available_ram_mb: int
    free_disk_mb: int
    cpu_threads: int

    def validate(self) -> None:
        if self.total_ram_mb <= 0:
            raise ValueError("total_ram_mb must be > 0")
        if not 0 <= self.available_ram_mb <= self.total_ram_mb:
            raise ValueError("available_ram_mb must be between 0 and total_ram_mb")
        if self.free_disk_mb < 0:
            raise ValueError("free_disk_mb must be >= 0")
        if self.cpu_threads <= 0:
            raise ValueError("cpu_threads must be > 0")


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    """Super-Ai reservation policy for a constrained machine."""

    system_reserved_ram_mb: int = 2000
    control_plane_reserved_ram_mb: int = 700
    safety_reserve_ram_mb: int = 700
    max_parallel_workers: int = 4

    def validate(self) -> None:
        for value, label in (
            (self.system_reserved_ram_mb, "system_reserved_ram_mb"),
            (self.control_plane_reserved_ram_mb, "control_plane_reserved_ram_mb"),
            (self.safety_reserve_ram_mb, "safety_reserve_ram_mb"),
        ):
            if value < 0:
                raise ValueError(f"{label} must be >= 0")
        if self.max_parallel_workers <= 0:
            raise ValueError("max_parallel_workers must be > 0")

    @property
    def reserved_ram_mb(self) -> int:
        return (
            self.system_reserved_ram_mb
            + self.control_plane_reserved_ram_mb
            + self.safety_reserve_ram_mb
        )


@dataclass(frozen=True, slots=True)
class Allocation:
    """Immutable reservation handle returned by the scheduler."""

    allocation_id: int
    capability_id: str
    reserved_ram_mb: int
    reserved_disk_mb: int
    reserved_cpu_threads: int


class ResourceLease:
    """Context-managed, idempotently releasable reservation lease."""

    def __init__(self, scheduler: "ResourceScheduler", allocation: Allocation) -> None:
        self._scheduler = scheduler
        self.allocation = allocation
        self._released = False

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        if self._released:
            return
        self._scheduler.release(self.allocation)
        self._released = True

    def __enter__(self) -> "ResourceLease":
        if self._released:
            raise RuntimeError("resource lease has already been released")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class ResourceScheduler:
    """Thread-safe deterministic peak-resource admission controller.

    Admission and reservation are one atomic operation. ResourceLease provides
    structured release so execution lifecycles cannot accidentally leak a
    reservation when an exception crosses a scope.
    """

    def __init__(
        self,
        snapshot: ResourceSnapshot,
        budget: ResourceBudget | None = None,
    ) -> None:
        snapshot.validate()
        self._snapshot = snapshot
        self._budget = budget or ResourceBudget()
        self._budget.validate()
        self._allocations: dict[int, Allocation] = {}
        self._next_id = 1
        self._lock = RLock()

    @property
    def execution_ram_capacity_mb(self) -> int:
        with self._lock:
            return max(0, self._snapshot.total_ram_mb - self._budget.reserved_ram_mb)

    @property
    def reserved_ram_mb(self) -> int:
        with self._lock:
            return sum(item.reserved_ram_mb for item in self._allocations.values())

    @property
    def reserved_disk_mb(self) -> int:
        with self._lock:
            return sum(item.reserved_disk_mb for item in self._allocations.values())

    @property
    def reserved_cpu_threads(self) -> int:
        with self._lock:
            return sum(item.reserved_cpu_threads for item in self._allocations.values())

    def _effective_available_ram_mb_locked(self) -> int:
        """Conservative RAM headroom after safety reserve and active reservations."""

        host_budget = max(
            0,
            self._snapshot.available_ram_mb - self._budget.safety_reserve_ram_mb,
        )
        internal_budget = max(
            0,
            self.execution_ram_capacity_mb - self.reserved_ram_mb,
        )
        return min(host_budget, internal_budget)

    def _can_admit_locked(
        self,
        contract: ResourceContract,
        task_constraints: TaskConstraints | None,
    ) -> bool:
        if len(self._allocations) >= self._budget.max_parallel_workers:
            return False

        if task_constraints is not None:
            task_constraints.validate()
            if contract.ram_hard_mb > task_constraints.max_ram_mb:
                return False
            if contract.disk_mb > task_constraints.max_disk_mb:
                return False
            if len(self._allocations) >= task_constraints.max_parallelism:
                return False

        return (
            contract.ram_hard_mb <= self._effective_available_ram_mb_locked()
            and contract.disk_mb
            <= self._snapshot.free_disk_mb - self.reserved_disk_mb
            and contract.cpu_threads
            <= self._snapshot.cpu_threads - self.reserved_cpu_threads
        )

    def can_admit(
        self,
        contract: ResourceContract,
        task_constraints: TaskConstraints | None = None,
    ) -> bool:
        contract.validate()
        with self._lock:
            return self._can_admit_locked(contract, task_constraints)

    def reserve(
        self,
        capability_id: str,
        contract: ResourceContract,
        task_constraints: TaskConstraints | None = None,
    ) -> Allocation:
        if not capability_id or capability_id.strip() != capability_id:
            raise ValueError("capability_id must be a non-empty trimmed string")

        contract.validate()

        with self._lock:
            if not self._can_admit_locked(contract, task_constraints):
                raise ResourceLimitError(
                    f"resource admission denied for {capability_id!r}: "
                    f"peak_ram={contract.ram_hard_mb}MB, "
                    f"available_execution_ram={self._effective_available_ram_mb_locked()}MB"
                )

            same_capability = sum(
                allocation.capability_id == capability_id
                for allocation in self._allocations.values()
            )
            if same_capability >= contract.max_concurrency:
                raise ResourceLimitError(
                    f"concurrency limit reached for {capability_id!r}: "
                    f"{contract.max_concurrency}"
                )

            allocation = Allocation(
                allocation_id=self._next_id,
                capability_id=capability_id,
                reserved_ram_mb=contract.ram_hard_mb,
                reserved_disk_mb=contract.disk_mb,
                reserved_cpu_threads=contract.cpu_threads,
            )
            self._allocations[allocation.allocation_id] = allocation
            self._next_id += 1
            return allocation

    def lease(
        self,
        capability_id: str,
        contract: ResourceContract,
        task_constraints: TaskConstraints | None = None,
    ) -> ResourceLease:
        """Atomically reserve resources and return a structured release handle."""

        return ResourceLease(
            self,
            self.reserve(capability_id, contract, task_constraints),
        )

    def release(self, allocation: Allocation) -> None:
        with self._lock:
            current = self._allocations.get(allocation.allocation_id)
            if current != allocation:
                raise KeyError(f"unknown allocation: {allocation.allocation_id}")
            del self._allocations[allocation.allocation_id]
