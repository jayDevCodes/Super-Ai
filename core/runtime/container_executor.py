from __future__ import annotations

from pathlib import Path
import subprocess
import threading
import uuid
from typing import BinaryIO, Mapping, Protocol

from .attestation import AttestationPolicy, SandboxAttestation, attest_container
from .execution import ProcessHandle, SandboxProcessHandle
from .preflight import AppleContainerPreflight, ImageIdentity, PreflightError
from .sandbox import AppleContainerSandbox, SandboxError, SandboxPlan
from .telemetry import AppleContainerStatsProvider, ContainerStatsCollector


class SandboxExecutionError(RuntimeError):
    """Raised when an isolated container cannot be safely started or cleaned."""


class CommandResult:
    """Small command result used by the container CLI adapter."""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ContainerCommandRunner(Protocol):
    """Host-side adapter for the Apple Container CLI."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout_seconds: float,
    ) -> CommandResult:
        ...

    def popen(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> ProcessHandle:
        ...


class SubprocessContainerCommandRunner:
    """Run the Apple Container CLI without a shell."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        timeout_seconds: float,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                list(command),
                cwd=Path(cwd).resolve(),
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxExecutionError("container CLI command failed") from exc

        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def popen(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> ProcessHandle:
        try:
            return subprocess.Popen(
                list(command),
                cwd=Path(cwd).resolve(),
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            raise SandboxExecutionError("container start failed") from exc


class AppleContainerProcessHandle:
    """Attach a process to an attested Apple Container lifecycle."""

    def __init__(
        self,
        *,
        process: ProcessHandle,
        container_id: str,
        runner: ContainerCommandRunner,
        cwd: Path,
        environment: Mapping[str, str],
        control_timeout_seconds: float,
        stop_grace_seconds: float,
        attestation: SandboxAttestation,
        telemetry: ContainerStatsCollector,
        telemetry_thread: threading.Thread | None,
        telemetry_stop: threading.Event | None,
        image_identity: ImageIdentity,
    ) -> None:
        self._process = process
        self._container_id = container_id
        self._runner = runner
        self._cwd = Path(cwd)
        self._environment = dict(environment)
        self._control_timeout_seconds = control_timeout_seconds
        self._stop_grace_seconds = stop_grace_seconds
        self._cleaned = False
        self._attestation = attestation
        self._telemetry = telemetry
        self._telemetry_thread = telemetry_thread
        self._telemetry_stop = telemetry_stop
        self._image_identity = image_identity

    @property
    def process(self) -> ProcessHandle:
        return self

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        if self.poll() is not None:
            return
        seconds = max(1, int(self._stop_grace_seconds + 0.999))
        try:
            self._runner.run(
                (
                    "container",
                    "stop",
                    "--signal",
                    "SIGTERM",
                    "--time",
                    str(seconds),
                    self._container_id,
                ),
                cwd=self._cwd,
                environment=self._environment,
                timeout_seconds=self._control_timeout_seconds,
            )
        except Exception:
            pass

    def kill(self) -> None:
        if self.poll() is not None:
            return
        try:
            self._runner.run(
                ("container", "kill", self._container_id),
                cwd=self._cwd,
                environment=self._environment,
                timeout_seconds=self._control_timeout_seconds,
            )
        except Exception:
            pass

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)

    @property
    def stdout(self) -> BinaryIO | None:
        return self._process.stdout

    @property
    def stderr(self) -> BinaryIO | None:
        return self._process.stderr

    @property
    def attestation(self) -> dict[str, object]:
        return self._attestation.as_dict()

    @property
    def image_digest(self) -> str:
        return self._image_identity.digest

    @property
    def telemetry(self) -> dict[str, object]:
        return self._telemetry.snapshot().as_dict()

    def cleanup(self) -> None:
        if self._cleaned:
            return

        if self._telemetry_stop is not None:
            self._telemetry_stop.set()
        if self._telemetry_thread is not None:
            self._telemetry_thread.join(timeout=0.25)

        try:
            result = self._runner.run(
                ("container", "delete", "--force", self._container_id),
                cwd=self._cwd,
                environment=self._environment,
                timeout_seconds=self._control_timeout_seconds,
            )
        except Exception as exc:
            raise SandboxExecutionError("container deletion failed") from exc

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").lower()
            if "not found" not in stderr and "no such" not in stderr:
                raise SandboxExecutionError(
                    "container deletion returned a non-zero status"
                )

        self._cleaned = True


class AppleContainerExecutor:
    """Create, attest, run, monitor, stop/kill, and delete one container."""

    backend_name = "apple-container"

    def __init__(
        self,
        *,
        planner: AppleContainerSandbox | None = None,
        runner: ContainerCommandRunner | None = None,
        create_timeout_seconds: float = 30.0,
        control_timeout_seconds: float = 10.0,
        telemetry_interval_seconds: float = 2.5,
    ) -> None:
        if create_timeout_seconds <= 0:
            raise ValueError("create_timeout_seconds must be > 0")
        if control_timeout_seconds <= 0:
            raise ValueError("control_timeout_seconds must be > 0")
        if telemetry_interval_seconds <= 0:
            raise ValueError("telemetry_interval_seconds must be > 0")

        self._planner = planner or AppleContainerSandbox()
        self._runner = runner or SubprocessContainerCommandRunner()
        self._create_timeout_seconds = create_timeout_seconds
        self._control_timeout_seconds = control_timeout_seconds
        self._telemetry_interval_seconds = telemetry_interval_seconds

    def launch(
        self,
        plan: SandboxPlan,
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> SandboxProcessHandle:
        self._validate_plan(plan)

        preflight = AppleContainerPreflight(
            self._runner,
            cwd=Path(cwd),
            environment=environment,
            timeout_seconds=self._control_timeout_seconds,
        )
        try:
            preflight.require_healthy_system()
            image_identity = preflight.resolve_image(plan.image)
        except PreflightError as exc:
            raise SandboxExecutionError(str(exc)) from exc

        expected_digest = plan.expected_image_digest or image_identity.digest
        if expected_digest != image_identity.digest:
            raise SandboxExecutionError(
                "preflight image digest does not match the pinned plan digest"
            )

        container_id = f"super-ai-{uuid.uuid4().hex[:24]}"
        create_command = self._planner.build_create_command(
            plan,
            container_id=container_id,
        )

        try:
            created = self._runner.run(
                create_command,
                cwd=Path(cwd),
                environment=environment,
                timeout_seconds=self._create_timeout_seconds,
            )
        except SandboxError:
            raise
        except Exception as exc:
            raise SandboxExecutionError("container creation failed") from exc

        if created.returncode != 0:
            stderr = created.stderr.decode("utf-8", errors="replace").strip()
            raise SandboxExecutionError(
                f"container creation returned {created.returncode}: {stderr[:512]}"
            )

        inspect = self._runner.run(
            ("container", "inspect", container_id),
            cwd=Path(cwd),
            environment=environment,
            timeout_seconds=self._control_timeout_seconds,
        )
        if inspect.returncode != 0:
            self._delete_after_failure(
                container_id=container_id,
                cwd=Path(cwd),
                environment=environment,
            )
            stderr = inspect.stderr.decode("utf-8", errors="replace").strip()
            raise SandboxExecutionError(
                f"container attestation inspect failed: {stderr[:512]}"
            )

        try:
            attestation = attest_container(
                inspect.stdout,
                container_id=container_id,
                image_reference=image_identity.reference,
                policy=AttestationPolicy(
                    expected_memory_bytes=plan.policy.memory_mb * 1024 * 1024,
                    expected_cpus=plan.policy.cpu_threads,
                    expected_image_digest=expected_digest,
                    expected_user=plan.policy.run_as_user or "",
                ),
                network_disabled=plan.policy.network == "disabled",
            )
        except Exception as exc:
            self._delete_after_failure(
                container_id=container_id,
                cwd=Path(cwd),
                environment=environment,
            )
            if isinstance(exc, SandboxExecutionError):
                raise
            raise SandboxExecutionError(
                f"container configuration attestation failed: {exc}"
            ) from exc

        start_command = ("container", "start", "--attach", container_id)
        try:
            process = self._runner.popen(
                start_command,
                cwd=Path(cwd),
                environment=environment,
            )
        except Exception as exc:
            self._delete_after_failure(
                container_id=container_id,
                cwd=Path(cwd),
                environment=environment,
            )
            raise SandboxExecutionError("container start failed") from exc

        collector = ContainerStatsCollector(
            AppleContainerStatsProvider(
                self._runner,
                cwd=Path(cwd),
                environment=environment,
                timeout_seconds=self._control_timeout_seconds,
            )
        )
        stop_event = threading.Event()
        telemetry_thread = threading.Thread(
            target=self._telemetry_loop,
            args=(collector, container_id, stop_event),
            daemon=True,
            name="super-ai-container-stats",
        )
        telemetry_thread.start()

        return AppleContainerProcessHandle(
            process=process,
            container_id=container_id,
            runner=self._runner,
            cwd=Path(cwd),
            environment=environment,
            control_timeout_seconds=self._control_timeout_seconds,
            stop_grace_seconds=plan.policy.timeout_seconds,
            attestation=attestation,
            telemetry=collector,
            telemetry_thread=telemetry_thread,
            telemetry_stop=stop_event,
            image_identity=ImageIdentity(
                reference=image_identity.reference,
                digest=expected_digest,
            ),
        )

    def _telemetry_loop(
        self,
        collector: ContainerStatsCollector,
        container_id: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.wait(self._telemetry_interval_seconds):
            try:
                collector.sample(container_id)
            except Exception:
                # Telemetry must never break or delay the workload.
                continue

    def _validate_plan(self, plan: SandboxPlan) -> None:
        if plan.backend != self.backend_name:
            raise SandboxExecutionError(
                f"unsupported sandbox backend: {plan.backend}"
            )
        if not plan.execution_ready:
            raise SandboxExecutionError("sandbox plan is not execution-ready")
        plan.policy.validate()

        if plan.policy.network == "disabled":
            if not _has_pair(plan.command, "--network", "none"):
                raise SandboxExecutionError(
                    "disabled-network plan must explicitly contain --network none"
                )
            if not _has_pair(plan.command, "--no-dns", "") and "--no-dns" not in plan.command:
                raise SandboxExecutionError(
                    "disabled-network plan must explicitly contain --no-dns"
                )

        if plan.policy.run_as_user is None:
            raise SandboxExecutionError(
                "untrusted sandbox execution requires an explicit non-root user"
            )

    def _delete_after_failure(
        self,
        *,
        container_id: str,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> None:
        try:
            result = self._runner.run(
                ("container", "delete", "--force", container_id),
                cwd=cwd,
                environment=environment,
                timeout_seconds=self._control_timeout_seconds,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").lower()
                if "not found" not in stderr and "no such" not in stderr:
                    raise SandboxExecutionError(
                        "container cleanup returned non-zero"
                    )
        except SandboxExecutionError:
            raise
        except Exception as exc:
            raise SandboxExecutionError("container cleanup failed") from exc


def _has_pair(command: tuple[str, ...], flag: str, value: str) -> bool:
    if value == "":
        return flag in command
    return any(
        command[index] == flag and command[index + 1] == value
        for index in range(len(command) - 1)
    )
