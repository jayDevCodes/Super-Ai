from __future__ import annotations

from pathlib import Path
from typing import Mapping

from core.contracts import ResourceContract, ResourceLease, ResourceScheduler, TaskConstraints

from .execution import (
    CleanupCallback,
    ExecutionController,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionVerifier,
)
from .sandbox import SandboxPlan


class ExecutionSessionError(RuntimeError):
    """Raised when an execution session is used outside its lifecycle."""


class ExecutionSession:
    """Bind one scheduler lease to one complete sandbox execution lifecycle.

    Resources are acquired before the controller can launch and released only
    after the controller has completed process termination, verification, and
    cleanup. The session is intentionally context-managed so exceptions cannot
    strand a reservation.
    """

    def __init__(
        self,
        scheduler: ResourceScheduler,
        controller: ExecutionController,
        *,
        capability_id: str,
        resource: ResourceContract,
        task_constraints: TaskConstraints | None = None,
    ) -> None:
        if not capability_id or capability_id.strip() != capability_id:
            raise ValueError("capability_id must be a non-empty trimmed string")
        resource.validate()
        if task_constraints is not None:
            task_constraints.validate()

        self._scheduler = scheduler
        self._controller = controller
        self._capability_id = capability_id
        self._resource = resource
        self._task_constraints = task_constraints
        self._lease: ResourceLease | None = None
        self._executed = False

    @property
    def active(self) -> bool:
        return self._lease is not None and not self._lease.released

    @property
    def lease(self) -> ResourceLease:
        if self._lease is None or self._lease.released:
            raise ExecutionSessionError("execution session is not active")
        return self._lease

    def __enter__(self) -> "ExecutionSession":
        if self.active:
            raise ExecutionSessionError("execution session is already active")
        if self._executed:
            raise ExecutionSessionError("execution session cannot be reused")
        self._lease = self._scheduler.lease(
            self._capability_id,
            self._resource,
            self._task_constraints,
        )
        return self

    def run(
        self,
        plan: SandboxPlan,
        *,
        policy: ExecutionPolicy | None = None,
        verifier: ExecutionVerifier | None = None,
        cleanup: CleanupCallback | None = None,
    ) -> ExecutionResult:
        if not self.active:
            raise ExecutionSessionError("execution session is not active")
        if self._executed:
            raise ExecutionSessionError("execution session can run only once")

        self._executed = True
        return self._controller.run(
            plan,
            policy=policy,
            verifier=verifier,
            cleanup=cleanup,
        )

    def close(self) -> None:
        if self._lease is not None:
            self._lease.release()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
