from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from core.runtime.pipeline import CapabilityExecution, CapabilityExecutionRequest, CapabilityRuntime
from core.runtime.cancellation import CancellationToken
from core.runtime.execution import ExecutionVerifier
from core.contracts import TaskConstraints
from core.router import RouteCandidate


class RuntimeRunnerError(RuntimeError):
    """Raised when a routed capability cannot be executed through CapabilityRuntime."""


@dataclass(frozen=True, slots=True)
class RuntimeStepOutput:
    capability_id: str
    version: str
    status: str
    stdout: str
    stderr: str
    verified: bool | None
    sandbox_attested: bool
    sandbox_image_digest: str | None
    cleanup_completed: bool
    telemetry: dict[str, object] | None


class CapabilityRuntimeStepRunner:
    """Adapt Brain DAG steps into the disposable CapabilityRuntime boundary."""

    def __init__(
        self,
        *,
        runtime: CapabilityRuntime,
        workspace_root: Path,
        task_constraints: TaskConstraints | None = None,
        verifier_factory: Callable[[RouteCandidate, object], ExecutionVerifier | None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._workspace_root = Path(workspace_root).resolve()
        self._workspace_root.mkdir(parents=True, exist_ok=True)
        self._task_constraints = task_constraints
        self._verifier_factory = verifier_factory

    def run(
        self,
        route: RouteCandidate,
        step,
        context: Mapping[str, object],
    ) -> RuntimeStepOutput:
        manifest = route.entry.manifest
        runtime_spec = manifest.runtime
        if runtime_spec is None:
            raise RuntimeRunnerError(
                f"capability {manifest.capability_id}@{manifest.version} has no runtime specification"
            )

        task_constraints = self._task_constraints
        if task_constraints is None:
            task_constraints = context.get("__task_constraints")
            if task_constraints is not None and not isinstance(
                task_constraints, TaskConstraints
            ):
                raise RuntimeRunnerError("context contains invalid task constraints")

        output_path = (
            self._workspace_root
            / manifest.capability_id.replace("/", "_")
            / uuid4().hex
        )

        verifier: ExecutionVerifier | None = None
        if self._verifier_factory is not None:
            verifier = self._verifier_factory(route, step)

        cancellation_token = context.get("__cancellation_token")
        if cancellation_token is not None and not isinstance(
            cancellation_token, CancellationToken
        ):
            raise RuntimeRunnerError("context contains invalid cancellation token")

        execution = self._runtime.execute(
            manifest=manifest,
            capability_spec=route.entry.spec,
            request=CapabilityExecutionRequest(
                image=runtime_spec.image,
                command=runtime_spec.command,
                output_path=output_path,
                workspace_root=self._workspace_root,
                timeout_seconds=runtime_spec.timeout_seconds,
                expected_image_digest=runtime_spec.expected_image_digest,
                cancellation_token=cancellation_token,
            ),
            task_constraints=task_constraints,
            verifier=verifier,
        )
        return _to_output(execution, manifest.version)


def _to_output(execution: CapabilityExecution, version: str) -> RuntimeStepOutput:
    result = execution.result
    return RuntimeStepOutput(
        capability_id=execution.staged.capability_id,
        version=version,
        status=result.status.value,
        stdout=result.stdout,
        stderr=result.stderr,
        verified=result.verified,
        sandbox_attested=result.sandbox_attested,
        sandbox_image_digest=result.sandbox_image_digest,
        cleanup_completed=result.cleanup_completed,
        telemetry=result.telemetry,
    )
