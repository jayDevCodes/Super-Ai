from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from core.contracts import ResourceContract, ResourceScheduler

from registry.runtime import RuntimeSpec

from .admission import ExecutionAdmissionGate
from .execution import ExecutionController, ExecutionPolicy, ExecutionResult
from .sandbox import AppleContainerSandbox, SandboxPolicy
from .session import ExecutionSession
from .stager import StagedArtifact


@dataclass(frozen=True, slots=True)
class SmokeTestResult:
    """Result of a real staged-capability sandbox smoke test."""

    passed: bool
    execution: ExecutionResult
    output_path: Path
    invariant_failures: tuple[str, ...]


class CapabilitySmokeTest:
    """Run one harmless staged capability through the real runtime boundary."""

    def __init__(
        self,
        *,
        scheduler: ResourceScheduler,
        controller: ExecutionController,
        sandbox: AppleContainerSandbox | None = None,
        admission_gate: ExecutionAdmissionGate | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._controller = controller
        self._sandbox = sandbox or AppleContainerSandbox()
        self._admission_gate = admission_gate

    def run(
        self,
        staged: StagedArtifact,
        *,
        image: str,
        expected_image_digest: str | None,
        command: Sequence[str],
        output_path: Path,
        memory_mb: int = 512,
        cpu_threads: int = 1,
        max_processes: int = 32,
        timeout_seconds: float = 30.0,
        verifier: Callable[[ExecutionResult], bool] | None = None,
    ) -> SmokeTestResult:
        staged.target_path.resolve().relative_to(staged.repository_root.resolve())
        output_path = Path(output_path).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        output_path.chmod(0o777)

        if self._admission_gate is not None:
            admission = self._admission_gate.evaluate(
                RuntimeSpec(
                    image=image,
                    command=tuple(command),
                    timeout_seconds=timeout_seconds,
                    expected_image_digest=expected_image_digest,
                    working_directory="/workspace",
                ),
                security_profile=ExecutionAdmissionGate.profile_for(
                    max_processes=max_processes,
                    network_enabled=False,
                ),
            )
            if not admission.accepted:
                raise ValueError("execution admission denied: " + "; ".join(admission.reasons))

        policy = SandboxPolicy(
            memory_mb=memory_mb,
            cpu_threads=cpu_threads,
            max_processes=max_processes,
            timeout_seconds=timeout_seconds,
            network="disabled",
            run_as_user="65532:65532",
            root_filesystem_read_only=True,
        )
        plan = self._sandbox.build_plan(
            image=image,
            command=tuple(command),
            source_path=staged.target_path,
            output_path=output_path,
            policy=policy,
            expected_image_digest=expected_image_digest,
        )

        resource = ResourceContract(
            ram_soft_mb=memory_mb,
            ram_hard_mb=memory_mb,
            disk_mb=0,
            cpu_threads=cpu_threads,
            max_concurrency=1,
        )

        verification = None
        if verifier is not None:
            class _Verifier:
                def verify(self, result: ExecutionResult) -> bool:
                    return bool(verifier(result))

            verification = _Verifier()

        with ExecutionSession(
            self._scheduler,
            self._controller,
            capability_id=staged.capability_id,
            resource=resource,
        ) as session:
            execution = session.run(
                plan,
                policy=ExecutionPolicy(timeout_seconds=timeout_seconds),
                verifier=verification,
            )

        failures: list[str] = []
        if not execution.sandbox_attested:
            failures.append("sandbox attestation evidence missing")
        if execution.sandbox_image_digest is None:
            failures.append("sandbox image digest evidence missing")
        if not execution.cleanup_completed:
            failures.append("sandbox cleanup did not complete")

        if not execution.telemetry:
            failures.append("sandbox telemetry evidence missing")
        else:
            if execution.telemetry.get("network_activity_observed"):
                failures.append("network activity was observed")

        return SmokeTestResult(
            passed=(
                execution.status.value == "completed"
                and execution.verified is not False
                and not failures
            ),
            execution=execution,
            output_path=output_path,
            invariant_failures=tuple(failures),
        )
