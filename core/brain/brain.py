from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from core.contracts import Task, TaskStep
from core.planner import StepExecution, TaskExecutionResult, TaskExecutor
from core.router import CapabilityRouter, RouteCandidate, RouteRequest
from core.policy import PolicyDecisionState
from core.audit import HashChainAuditStore


class BrainError(RuntimeError):
    """Raised when planning or executing a task is unsafe or ambiguous."""


@dataclass(frozen=True, slots=True)
class PlannedStep:
    step: TaskStep
    route: RouteCandidate


@dataclass(frozen=True, slots=True)
class BrainPlan:
    task_id: str
    steps: tuple[PlannedStep, ...]
    requires_confirmation: bool


class StepRunner(Protocol):
    def run(
        self,
        route: RouteCandidate,
        step: TaskStep,
        context: Mapping[str, object],
    ) -> object:
        ...


class Brain:
    """Lightweight control-plane orchestrator over routing and task execution."""

    def __init__(
        self,
        *,
        router: CapabilityRouter,
        runner: StepRunner,
        max_workers: int = 4,
        audit_store: HashChainAuditStore | None = None,
    ) -> None:
        self._router = router
        self._runner = runner
        self._max_workers = max_workers
        self._audit = audit_store

    def plan(self, task: Task) -> BrainPlan:
        task.validate()
        planned: list[PlannedStep] = []
        confirmation = False

        for step in task.steps:
            route = self._router.select(
                RouteRequest(
                    goal=step.description,
                    capability_id=step.capability_id,
                    task_constraints=task.constraints,
                ),
                include_confirmation=True,
            )
            if route.policy_state is PolicyDecisionState.DENY:
                raise BrainError(
                    f"step {step.step_id!r} is denied by policy"
                )
            if route.policy_state is PolicyDecisionState.CONFIRM:
                confirmation = True
            planned.append(PlannedStep(step=step, route=route))

        result = BrainPlan(
            task_id=task.task_id,
            steps=tuple(planned),
            requires_confirmation=confirmation,
        )
        self._record(
            "brain.plan_created",
            {
                "task_id": task.task_id,
                "step_count": len(planned),
                "requires_confirmation": confirmation,
            },
        )
        return result

    def execute(
        self,
        task: Task,
        *,
        confirmed: bool = False,
        initial_context: Mapping[str, object] | None = None,
    ) -> TaskExecutionResult:
        plan = self.plan(task)
        if plan.requires_confirmation and not confirmed:
            raise BrainError("task requires human confirmation before execution")

        routes = {item.step.step_id: item.route for item in plan.steps}

        def handler(step: TaskStep, context: Mapping[str, object]) -> object:
            route = routes.get(step.step_id)
            if route is None:
                raise BrainError(f"missing route for step {step.step_id!r}")
            output = self._runner.run(route, step, context)
            self._record(
                "brain.step_completed",
                {
                    "step_id": step.step_id,
                    "capability_id": route.entry.manifest.capability_id,
                    "policy_state": route.policy_state.value,
                },
            )
            return output

        executor = TaskExecutor(
            handler=handler,
            max_workers=self._max_workers,
        )

        self._record(
            "brain.execution_started",
            {
                "task_id": task.task_id,
                "confirmed": confirmed,
            },
        )
        result = executor.execute(
            task,
            initial_context=initial_context,
        )
        self._record(
            "brain.execution_finished",
            {
                "task_id": task.task_id,
                "succeeded": result.succeeded,
                "failed_step": result.failed_step,
            },
        )
        return result

    def _record(self, event_name: str, attributes: Mapping[str, object]) -> None:
        if self._audit is not None:
            self._audit.append(event_name, attributes)
