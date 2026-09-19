from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import subprocess
import uuid
from typing import BinaryIO, Mapping, Protocol

from .execution import ProcessHandle, SandboxProcessHandle
from .sandbox import AppleContainerSandbox, SandboxError, SandboxPlan


class SandboxExecutionError(RuntimeError):
    """Raised when an isolated container cannot be safely started or cleaned."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Small command result used by the container CLI adapter."""

    returncode: int
    stdout: bytes
    stderr: bytes


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
    """Attach a ProcessHandle to a named Apple Container lifecycle."""

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
    ) -> None:
        self._process = process
        self._container_id = container_id
        self._runner = runner
        self._cwd = Path(cwd)
        self._environment = dict(environment)
        self._control_timeout_seconds = control_timeout_seconds
        self._stop_grace_seconds = stop_grace_seconds
        self._cleaned = False

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
            # The controller will still wait/kill the attached CLI process.
            # Cleanup is responsible for the final container deletion.
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

    def cleanup(self) -> None:
        if self._cleaned:
            return

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
    """Create, start, stop/kill, and delete one Apple Container per execution."""

    backend_name = "apple-container"

    def __init__(
        self,
        *,
        planner: AppleContainerSandbox | None = None,
        runner: ContainerCommandRunner | None = None,
        create_timeout_seconds: float = 30.0,
        control_timeout_seconds: float = 10.0,
    ) -> None:
        if create_timeout_seconds <= 0:
            raise ValueError("create_timeout_seconds must be > 0")
        if control_timeout_seconds <= 0:
            raise ValueError("control_timeout_seconds must be > 0")

        self._planner = planner or AppleContainerSandbox()
        self._runner = runner or SubprocessContainerCommandRunner()
        self._create_timeout_seconds = create_timeout_seconds
        self._control_timeout_seconds = control_timeout_seconds

    def launch(
        self,
        plan: SandboxPlan,
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> SandboxProcessHandle:
        self._validate_plan(plan)

        container_id = f"super-ai-{uuid.uuid4().hex[:24]}"
        create_command = self._planner.build_create_command(
            plan,
            container_id=container_id,
        )
        start_command = ("container", "start", "--attach", container_id)

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

        try:
            process = self._runner.popen(
                start_command,
                cwd=Path(cwd),
                environment=environment,
            )
        except Exception as exc:
            self._delete_after_start_failure(
                container_id=container_id,
                cwd=Path(cwd),
                environment=environment,
            )
            raise SandboxExecutionError("container start failed") from exc

        return AppleContainerProcessHandle(
            process=process,
            container_id=container_id,
            runner=self._runner,
            cwd=Path(cwd),
            environment=environment,
            control_timeout_seconds=self._control_timeout_seconds,
            stop_grace_seconds=plan.policy.timeout_seconds,
        )

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

    def _delete_after_start_failure(
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
                        "container cleanup after start failure returned non-zero"
                    )
        except SandboxExecutionError:
            raise
        except Exception as exc:
            raise SandboxExecutionError(
                "container cleanup after start failure failed"
            ) from exc


def _has_pair(command: tuple[str, ...], flag: str, value: str) -> bool:
    return any(
        command[index] == flag and command[index + 1] == value
        for index in range(len(command) - 1)
    )
