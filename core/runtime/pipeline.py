from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Sequence

from core.contracts import (
    CapabilitySpec,
    ResourceScheduler,
    OutputContract,
    TaskConstraints,
    WorkspaceContract,
    WorkspaceContractError,
)

from core.policy import CapabilityPolicyEngine, PolicyDecisionState
from core.audit import HashChainAuditStore
from core.observability import TraceContext

from .cancellation import CancellationToken
from .execution import (
    ExecutionController,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    ExecutionVerifier,
)
from .sandbox import AppleContainerSandbox, SandboxPolicy
from registry.resolver import GitHubSourceResolver
from .session import ExecutionSession
from .stager import CapabilityStager, StagedArtifact


class CapabilityPipelineError(RuntimeError):
    """Raised when a capability cannot complete the end-to-end runtime pipeline."""


@dataclass(frozen=True, slots=True)
class CapabilityExecutionRequest:
    """Immutable inputs for one disposable capability execution."""

    image: str
    command: tuple[str, ...]
    output_path: Path
    workspace_root: Path
    timeout_seconds: float | None = None
    expected_image_digest: str | None = None
    trace_context: TraceContext | None = None
    cancellation_token: CancellationToken | None = None
    output_contract: OutputContract | None = None

    def validate(self) -> None:
        if not self.image or self.image.strip() != self.image:
            raise ValueError("image must be a non-empty trimmed string")
        if not self.command or any(not part for part in self.command):
            raise ValueError("command must be a non-empty argv")
        if self.output_path is None:
            raise ValueError("output_path must be provided")
        if self.workspace_root is None:
            raise ValueError("workspace_root must be provided")
        if self.output_contract is not None:
            self.output_contract.validate()
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0 when provided")


@dataclass(frozen=True, slots=True)
class CapabilityExecution:
    """Result plus staged-source evidence for one disposable execution."""

    result: ExecutionResult
    staged: StagedArtifact


class CapabilityRuntime:
    """Wire immutable resolution, secure staging, sandboxing, execution, and cleanup."""

    def __init__(
        self,
        *,
        scheduler: ResourceScheduler,
        stager: CapabilityStager,
        controller: ExecutionController,
        resolver: GitHubSourceResolver | None = None,
        policy_engine: CapabilityPolicyEngine | None = None,
        audit_store: HashChainAuditStore | None = None,
        sandbox: AppleContainerSandbox | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._stager = stager
        self._controller = controller
        self._resolver = resolver or GitHubSourceResolver()
        self._policy_engine = policy_engine or CapabilityPolicyEngine()
        self._audit = audit_store
        self._sandbox = sandbox or AppleContainerSandbox()

    def execute(
        self,
        *,
        manifest,
        capability_spec: CapabilitySpec,
        request: CapabilityExecutionRequest,
        task_constraints: TaskConstraints | None = None,
        verifier: ExecutionVerifier | None = None,
    ) -> CapabilityExecution:
        manifest.validate()
        capability_spec.validate()
        request.validate()

        if capability_spec.verification_required and verifier is None:
            raise CapabilityPipelineError(
                "capability requires an explicit verifier before execution"
            )

        trace = request.trace_context or TraceContext.new_root()

        if manifest.capability_id != capability_spec.capability_id:
            raise CapabilityPipelineError(
                "manifest and capability spec capability_id values do not match"
            )
        if manifest.version != capability_spec.version:
            raise CapabilityPipelineError(
                "manifest and capability spec versions do not match"
            )

        decision = self._policy_engine.evaluate(
            capability_spec,
            task_constraints,
        )
        if decision.state is PolicyDecisionState.DENY:
            self._record(
                "runtime.policy_denied",
                {
                    "capability_id": capability_spec.capability_id,
                    "version": capability_spec.version,
                    "reasons": list(decision.reasons),
                },
                trace_context=trace,
            )
            raise CapabilityPipelineError(
                "capability execution denied: " + "; ".join(decision.reasons)
            )
        if (
            decision.state is PolicyDecisionState.CONFIRM
            and (task_constraints is None
                 or task_constraints.require_confirmation_for_consequential_actions)
        ):
            raise CapabilityPipelineError(
                "capability execution requires human confirmation"
            )

        timeout_seconds = request.timeout_seconds or 60.0
        if timeout_seconds <= 0:
            raise CapabilityPipelineError("execution timeout must be > 0")

        output_contract = request.output_contract
        runtime_spec = getattr(manifest, "runtime", None)
        if output_contract is None and runtime_spec is not None:
            output_contract = runtime_spec.output_contract
        if output_contract is None:
            output_contract = OutputContract()
        try:
            output_contract.validate()
        except ValueError as exc:
            raise CapabilityPipelineError(
                f"output contract rejected execution: {exc}"
            ) from exc

        workspace_root = Path(request.workspace_root).expanduser()
        try:
            workspace_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CapabilityPipelineError("workspace root could not be prepared") from exc

        output_path = Path(request.output_path).expanduser()

        self._record(
            "runtime.execution_requested",
            {
                "capability_id": capability_spec.capability_id,
                "version": capability_spec.version,
                "image": request.image,
            },
            trace_context=trace,
        )

        with TemporaryDirectory(
            prefix=f"super-ai-runtime-{manifest.capability_id.replace('.', '-')}-"
        ) as temp:
            workdir = Path(temp)
            source_plan = self._resolver.resolve(manifest)
            staged = self._stager.stage(manifest, source_plan, workdir)

            network = decision.network

            network_name = None
            if network == "enabled":
                network_name = "super-ai-runtime"

            sandbox_policy = SandboxPolicy(
                memory_mb=capability_spec.resource.ram_hard_mb,
                cpu_threads=capability_spec.resource.cpu_threads,
                max_processes=64,
                timeout_seconds=timeout_seconds,
                network=network,
                network_name=network_name,
                run_as_user="65532:65532",
                root_filesystem_read_only=True,
            )

            try:
                workspace = WorkspaceContract(
                    root=workspace_root,
                    source_path=staged.target_path,
                    output_path=output_path,
                )
                workspace.ensure_output_directory()
            except WorkspaceContractError as exc:
                raise CapabilityPipelineError(
                    f"workspace contract rejected execution: {exc}"
                ) from exc

            plan = self._sandbox.build_plan(
                image=request.image,
                command=request.command,
                source_path=staged.target_path,
                output_path=output_path,
                policy=sandbox_policy,
                workspace=workspace,
                expected_image_digest=request.expected_image_digest,
            )

            self._record(
                "runtime.execution_started",
                {
                    "capability_id": capability_spec.capability_id,
                    "version": capability_spec.version,
                },
                trace_context=trace.child(),
            )

            with ExecutionSession(
                self._scheduler,
                self._controller,
                capability_id=capability_spec.capability_id,
                resource=capability_spec.resource,
                task_constraints=task_constraints,
            ) as session:
                result = session.run(
                    plan,
                    policy=ExecutionPolicy(timeout_seconds=timeout_seconds),
                    verifier=verifier,
                    cancellation_token=request.cancellation_token,
                )

            inspection = output_contract.inspect(output_path)
            result = replace(result, output_inspection=inspection)
            if (
                not inspection.passed
                and result.status is ExecutionStatus.COMPLETED
            ):
                result = replace(
                    result,
                    status=ExecutionStatus.VERIFICATION_FAILED,
                    verified=False,
                )

            self._record(
                "runtime.execution_finished",
                {
                    "capability_id": capability_spec.capability_id,
                    "version": capability_spec.version,
                    "status": result.status.value,
                    "verified": result.verified,
                    "cleanup_completed": result.cleanup_completed,
                    "sandbox_attested": result.sandbox_attested,
                    "image_digest": result.sandbox_image_digest,
                },
                trace_context=trace.child(),
            )
            return CapabilityExecution(result=result, staged=staged)

    def _record(
        self,
        event_name: str,
        attributes: dict[str, object],
        *,
        trace_context: TraceContext | None = None,
    ) -> None:
        if self._audit is None:
            return
        enriched = dict(attributes)
        if trace_context is not None:
            enriched.update(trace_context.as_attributes())
        self._audit.append(event_name, enriched)
