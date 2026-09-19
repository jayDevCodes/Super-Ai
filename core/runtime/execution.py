from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import BinaryIO, Callable, Mapping, Protocol

from .sandbox import SandboxPlan


class ExecutionError(RuntimeError):
    """Raised when execution cannot be started or safely completed."""


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    VERIFICATION_FAILED = "verification_failed"
    CLEANUP_FAILED = "cleanup_failed"


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Runtime limits applied by the execution controller."""

    timeout_seconds: float = 60.0
    max_output_bytes: int = 1024 * 1024
    max_error_bytes: int = 1024 * 1024
    termination_grace_seconds: float = 2.0

    def validate(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be > 0")
        if self.max_error_bytes <= 0:
            raise ValueError("max_error_bytes must be > 0")
        if self.termination_grace_seconds < 0:
            raise ValueError("termination_grace_seconds must be >= 0")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Bounded result record for one sandbox execution."""

    status: ExecutionStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    verified: bool | None
    cleanup_completed: bool
    sandbox_attested: bool = False
    sandbox_image_digest: str | None = None
    telemetry: Mapping[str, object] | None = None


class ProcessHandle(Protocol):
    """Minimal process lifecycle contract used by the controller."""

    @property
    def returncode(self) -> int | None:
        ...

    def poll(self) -> int | None:
        ...

    def terminate(self) -> None:
        ...

    def kill(self) -> None:
        ...

    def wait(self, timeout: float | None = None) -> int:
        ...

    @property
    def stdout(self) -> BinaryIO | None:
        ...

    @property
    def stderr(self) -> BinaryIO | None:
        ...


class ProcessLauncher(Protocol):
    """Launches an already-sandboxed argv without a shell."""

    def launch(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> ProcessHandle:
        ...


class SandboxProcessHandle(Protocol):
    """Process plus sandbox lifecycle owned by an execution backend."""

    @property
    def process(self) -> ProcessHandle:
        ...

    def cleanup(self) -> None:
        ...


class SandboxExecutor(Protocol):
    """Launches a complete SandboxPlan inside an isolated backend."""

    def launch(
        self,
        plan: SandboxPlan,
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> SandboxProcessHandle:
        ...


class ExecutionVerifier(Protocol):
    """Checks an execution result before it is accepted."""

    def verify(self, result: ExecutionResult) -> bool:
        ...


CleanupCallback = Callable[[], None]


@dataclass(slots=True)
class _OutputCapture:
    limit: int
    chunks: bytearray
    truncated: bool = False

    def read_from(self, stream: BinaryIO) -> None:
        try:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    return
                remaining = self.limit - len(self.chunks)
                if remaining > 0:
                    self.chunks.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        except Exception:
            self.truncated = True

    def text(self) -> str:
        return bytes(self.chunks).decode("utf-8", errors="replace")


class SubprocessLauncher:
    """Explicit host launcher for trusted local commands.

    Untrusted capabilities must use a SandboxExecutor instead. Keeping the
    launcher explicit prevents the controller from silently falling back to
    host execution.
    """

    def launch(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: Mapping[str, str],
    ) -> ProcessHandle:
        if not command:
            raise ExecutionError("command must not be empty")
        cwd = Path(cwd).resolve()
        if not cwd.is_dir():
            raise ExecutionError("execution cwd must be an existing directory")
        try:
            return subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=(os.name == "posix"),
                close_fds=True,
            )
        except OSError as exc:
            raise ExecutionError("host process launch failed") from exc


class ExecutionController:
    """Runs sandbox plans with bounded output, timeout, verification, and cleanup."""

    def __init__(
        self,
        launcher: ProcessLauncher | None = None,
        environment: Mapping[str, str] | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        if launcher is not None and sandbox_executor is not None:
            raise ValueError("choose launcher or sandbox_executor, not both")
        self._launcher = launcher
        self._sandbox_executor = sandbox_executor
        self._environment = {
            "PATH": os.environ.get(
                "PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
            )
        }
        if environment is not None:
            self._environment.update(environment)

    def run(
        self,
        plan: SandboxPlan,
        *,
        policy: ExecutionPolicy | None = None,
        verifier: ExecutionVerifier | None = None,
        cleanup: CleanupCallback | None = None,
    ) -> ExecutionResult:
        active_policy = policy or ExecutionPolicy(
            timeout_seconds=plan.policy.timeout_seconds
        )
        active_policy.validate()

        if active_policy.timeout_seconds > plan.policy.timeout_seconds:
            raise ExecutionError(
                "execution timeout cannot exceed the sandbox timeout"
            )

        if not plan.execution_ready:
            raise ExecutionError(
                "sandbox plan is not execution-ready; verified network/isolation policy required"
            )

        if not plan.command:
            raise ExecutionError("sandbox plan command must not be empty")

        if self._launcher is None and self._sandbox_executor is None:
            raise ExecutionError("no execution backend configured")

        started = time.monotonic()
        stdout_capture = _OutputCapture(active_policy.max_output_bytes, bytearray())
        stderr_capture = _OutputCapture(active_policy.max_error_bytes, bytearray())
        process: ProcessHandle | None = None
        sandbox_handle: SandboxProcessHandle | None = None
        readers: list[threading.Thread] = []
        timed_out = False
        result: ExecutionResult | None = None
        execution_error: Exception | None = None
        cleanup_error: Exception | None = None

        try:
            if self._sandbox_executor is not None:
                sandbox_handle = self._sandbox_executor.launch(
                    plan,
                    cwd=plan.output_path,
                    environment=self._environment,
                )
                process = sandbox_handle.process
            else:
                process = self._launcher.launch(  # type: ignore[union-attr]
                    plan.command,
                    cwd=plan.output_path,
                    environment=self._environment,
                )

            stdout_stream = process.stdout
            stderr_stream = process.stderr
            if stdout_stream is None or stderr_stream is None:
                raise ExecutionError(
                    "execution process did not expose stdout/stderr pipes"
                )

            readers = [
                threading.Thread(
                    target=stdout_capture.read_from,
                    args=(stdout_stream,),
                    daemon=True,
                    name="super-ai-stdout-reader",
                ),
                threading.Thread(
                    target=stderr_capture.read_from,
                    args=(stderr_stream,),
                    daemon=True,
                    name="super-ai-stderr-reader",
                ),
            ]
            for reader in readers:
                reader.start()

            try:
                exit_code = process.wait(timeout=active_policy.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._request_termination(process)
                try:
                    exit_code = process.wait(
                        timeout=active_policy.termination_grace_seconds
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    exit_code = process.wait(
                        timeout=max(active_policy.termination_grace_seconds, 0.1)
                    )

            for reader in readers:
                reader.join(
                    timeout=active_policy.termination_grace_seconds + 0.5
                )

            status = (
                ExecutionStatus.TIMED_OUT
                if timed_out
                else (
                    ExecutionStatus.COMPLETED
                    if exit_code == 0
                    else ExecutionStatus.FAILED
                )
            )

            result = ExecutionResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout_capture.text(),
                stderr=stderr_capture.text(),
                duration_seconds=time.monotonic() - started,
                timed_out=timed_out,
                stdout_truncated=stdout_capture.truncated,
                stderr_truncated=stderr_capture.truncated,
                verified=None,
                cleanup_completed=False,
            )

            if verifier is not None:
                try:
                    verified = bool(verifier.verify(result))
                except Exception:
                    verified = False
                if not verified:
                    result = _with_status(
                        result,
                        ExecutionStatus.VERIFICATION_FAILED,
                        verified=False,
                    )
                else:
                    result = _with_status(result, result.status, verified=True)

        except Exception as exc:
            execution_error = exc if isinstance(exc, Exception) else Exception(str(exc))
        finally:
            if process is not None and process.poll() is None:
                self._request_termination(process)
                try:
                    process.wait(timeout=max(active_policy.termination_grace_seconds, 0.1))
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                        process.wait(timeout=0.5)
                    except (OSError, subprocess.TimeoutExpired):
                        pass

            for reader in readers:
                reader.join(timeout=max(active_policy.termination_grace_seconds, 0.2))

            if sandbox_handle is not None:
                try:
                    sandbox_handle.cleanup()
                except Exception as exc:
                    cleanup_error = exc

            if cleanup is not None:
                try:
                    cleanup()
                except Exception as exc:
                    cleanup_error = exc

        if result is not None and sandbox_handle is not None:
            result = _with_runtime_data(result, sandbox_handle)

        if cleanup_error is not None:
            if result is not None:
                return _with_status(
                    result,
                    ExecutionStatus.CLEANUP_FAILED,
                    cleanup_completed=False,
                )
            raise ExecutionError("execution cleanup failed") from cleanup_error

        if execution_error is not None:
            raise execution_error

        if result is None:
            raise ExecutionError("execution produced no result")

        return _with_status(
            result,
            result.status,
            cleanup_completed=True,
        )

    @staticmethod
    def _request_termination(process: ProcessHandle) -> None:
        if process.poll() is not None:
            return

        if os.name == "posix" and isinstance(process, subprocess.Popen):
            try:
                os.killpg(process.pid, signal.SIGTERM)
                return
            except (ProcessLookupError, OSError):
                pass

        process.terminate()


def _with_runtime_data(
    result: ExecutionResult,
    sandbox_handle: SandboxProcessHandle,
) -> ExecutionResult:
    attestation = getattr(sandbox_handle, "attestation", None)
    image_digest = getattr(sandbox_handle, "image_digest", None)
    telemetry = getattr(sandbox_handle, "telemetry", None)
    return ExecutionResult(
        status=result.status,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
        verified=result.verified,
        cleanup_completed=result.cleanup_completed,
        sandbox_attested=bool(attestation),
        sandbox_image_digest=image_digest,
        telemetry=telemetry,
    )


def _with_runtime_data(
    result: ExecutionResult,
    sandbox_handle: SandboxProcessHandle,
) -> ExecutionResult:
    attestation = getattr(sandbox_handle, "attestation", None)
    image_digest = getattr(sandbox_handle, "image_digest", None)
    telemetry = getattr(sandbox_handle, "telemetry", None)
    return ExecutionResult(
        status=result.status,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
        verified=result.verified,
        cleanup_completed=result.cleanup_completed,
        sandbox_attested=bool(attestation),
        sandbox_image_digest=image_digest,
        telemetry=telemetry,
    )


def _with_status(
    result: ExecutionResult,
    status: ExecutionStatus,
    *,
    verified: bool | None = None,
    cleanup_completed: bool | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        status=status,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
        verified=result.verified if verified is None else verified,
        cleanup_completed=(
            result.cleanup_completed
            if cleanup_completed is None
            else cleanup_completed
        ),
        sandbox_attested=result.sandbox_attested,
        sandbox_image_digest=result.sandbox_image_digest,
        telemetry=result.telemetry,
    )
