from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from core.contracts import Task, TaskStep
from core.planner import StepExecution, TaskExecutionResult, TaskExecutor
from core.router import CapabilityRouter, RouteCandidate, RouteRequest, RoutingError
from core.security import EmergencyAuthority, EmergencyAuthorityError, OwnerAuthorization, OwnerAuthorizationError, OwnerOverrideGrant
from core.policy import PolicyDecisionState
from core.audit import HashChainAuditStore
from core.observability import TraceContext
from core.models import TaskModelManager


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
    trace_context: TraceContext


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
        model_manager: TaskModelManager | None = None,
        owner_authorization: OwnerAuthorization | None = None,
        emergency_authority: EmergencyAuthority | None = None,
    ) -> None:
        self._router = router
        self._runner = runner
        self._max_workers = max_workers
        self._audit = audit_store
        self._model_manager = model_manager
        self._owner_authorization = owner_authorization
        self._emergency_authority = emergency_authority

    def plan(
        self,
        task: Task,
        *,
        trace_context: TraceContext | None = None,
    ) -> BrainPlan:
        task.validate()
        trace = trace_context or TraceContext.new_root()
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
            trace_context=trace,
        )
        self._record(
            "brain.plan_created",
            {
                "task_id": task.task_id,
                "step_count": len(planned),
                "requires_confirmation": confirmation,
            },
            trace_context=trace,
        )
        return result

    def _plan_with_owner_decision(
        self,
        task: Task,
        *,
        trace_context: TraceContext | None = None,
    ) -> BrainPlan:
        task.validate()
        trace = trace_context or TraceContext.new_root()
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
                owner_override=True,
            )
            if route.policy_state is PolicyDecisionState.DENY:
                raise BrainError(f"step {step.step_id!r} remains denied")
            if route.policy_state is PolicyDecisionState.CONFIRM:
                confirmation = True
            planned.append(PlannedStep(step=step, route=route))

        result = BrainPlan(
            task_id=task.task_id,
            steps=tuple(planned),
            requires_confirmation=confirmation,
            trace_context=trace,
        )
        self._record(
            "brain.plan_created_with_owner_decision",
            {
                "task_id": task.task_id,
                "step_count": len(planned),
                "requires_confirmation": confirmation,
            },
            trace_context=trace,
        )
        return result

    def execute(
        self,
        task: Task,
        *,
        confirmed: bool = False,
        initial_context: Mapping[str, object] | None = None,
        owner_override_code: str | None = None,
    ) -> TaskExecutionResult:
        trace = TraceContext.new_root()
        owner_grant: OwnerOverrideGrant | None = None
        if self._emergency_authority is not None:
            try:
                self._emergency_authority.assert_task_allowed(task.task_id)
            except EmergencyAuthorityError as exc:
                raise BrainError(str(exc)) from exc

        try:
            plan = self.plan(task, trace_context=trace)
        except RoutingError:
            if owner_override_code is None or self._owner_authorization is None:
                raise
            scope = OwnerAuthorization.scope_for_task(task.task_id, task.goal)
            try:
                owner_grant = self._owner_authorization.authenticate(
                    owner_override_code,
                    scope_digest=scope,
                )
                self._owner_authorization.consume(owner_grant, scope_digest=scope)
            except (OwnerAuthorizationError, ValueError, TypeError) as exc:
                raise BrainError("owner override authentication failed") from exc

            self._record(
                "brain.owner_override_authenticated",
                {
                    "task_id": task.task_id,
                    "scope_digest": scope,
                    "proof_id": owner_grant.proof_id,
                },
                trace_context=trace,
            )
            plan = self._plan_with_owner_decision(
                task,
                trace_context=trace,
            )
            for planned_step in plan.steps:
                if planned_step.route.policy_state is PolicyDecisionState.OWNER_OVERRIDE:
                    self._record(
                        "brain.owner_policy_decision",
                        {
                            "task_id": task.task_id,
                            "step_id": planned_step.step.step_id,
                            "capability_id": planned_step.route.entry.manifest.capability_id,
                            "proof_id": owner_grant.proof_id if owner_grant else "",
                            "original_policy_reasons": planned_step.route.policy_reasons,
                        },
                        trace_context=trace,
                    )

        if plan.requires_confirmation and not confirmed and owner_grant is None:
            raise BrainError("task requires human confirmation before execution")

        routes = {item.step.step_id: item.route for item in plan.steps}

        def handler(step: TaskStep, context: Mapping[str, object]) -> object:
            if self._emergency_authority is not None:
                try:
                    self._emergency_authority.assert_task_allowed(task.task_id)
                except EmergencyAuthorityError as exc:
                    raise BrainError(str(exc)) from exc
            route = routes.get(step.step_id)
            if route is None:
                raise BrainError(f"missing route for step {step.step_id!r}")
            if self._model_manager is not None and bool(
                getattr(self._runner, "requires_model", False)
            ):
                with self._model_manager.use_for_task(
                    step.description,
                    max_ram_mb=task.constraints.max_ram_mb,
                    max_disk_mb=task.constraints.max_disk_mb,
                    reserved_ram_mb=route.entry.spec.resource.ram_hard_mb,
                    reserved_disk_mb=route.entry.spec.resource.disk_mb,
                ) as selection:
                    step_context = dict(context)
                    step_context["__model_name"] = selection.model
                    step_context["__model_reason"] = selection.reason
                    self._record(
                        "brain.model_selected",
                        {
                            "step_id": step.step_id,
                            "model": selection.model,
                            "reason": selection.reason,
                        },
                        trace_context=trace,
                    )
                    output = self._runner.run(route, step, step_context)
            else:
                output = self._runner.run(route, step, context)
            self._record(
                "brain.step_completed",
                {
                    "step_id": step.step_id,
                    "capability_id": route.entry.manifest.capability_id,
                    "policy_state": route.policy_state.value,
                },
                trace_context=trace,
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
            trace_context=trace,
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
            trace_context=trace,
        )
        return result

    def execute_emergency(self, request, *, owner_code: str) -> OwnerOverrideGrant:
        if self._emergency_authority is None:
            raise BrainError("emergency authority is not configured")
        try:
            return self._emergency_authority.execute(request, owner_code=owner_code)
        except EmergencyAuthorityError as exc:
            raise BrainError("emergency command was not accepted") from exc

    def _record(
        self,
        event_name: str,
        attributes: Mapping[str, object],
        *,
        trace_context: TraceContext | None = None,
    ) -> None:
        if self._audit is None:
            return
        enriched = dict(attributes)
        if trace_context is not None:
            enriched.update(trace_context.as_attributes())
        self._audit.append(event_name, enriched)
