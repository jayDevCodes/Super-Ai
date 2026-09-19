from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import platform
import shutil
from typing import Mapping, Protocol

from .container_executor import CommandResult, SubprocessContainerCommandRunner


class RuntimeProbeState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RuntimeProbeResult:
    """Observed host/runtime readiness for Apple Container integration."""

    state: RuntimeProbeState
    operating_system: str
    architecture: str
    container_cli: str | None
    system_status: Mapping[str, object] | None
    reason: str

    @property
    def available(self) -> bool:
        return self.state is RuntimeProbeState.AVAILABLE


class RuntimeProbeRunner(Protocol):
    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd,
        environment: Mapping[str, str],
        timeout_seconds: float,
    ) -> CommandResult:
        ...


class RuntimeProbe:
    """Detect whether the real Apple Container runtime is usable."""

    def __init__(
        self,
        *,
        runner: RuntimeProbeRunner | None = None,
        cwd=".",
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = runner or SubprocessContainerCommandRunner()
        self._cwd = cwd
        self._environment = {
            "PATH": os.environ.get(
                "PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
            )
        }
        if environment is not None:
            self._environment.update(environment)
        self._timeout_seconds = timeout_seconds

    def probe(self) -> RuntimeProbeResult:
        operating_system = platform.system()
        architecture = platform.machine().lower()

        if operating_system != "Darwin":
            return RuntimeProbeResult(
                state=RuntimeProbeState.UNAVAILABLE,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=None,
                system_status=None,
                reason="Apple Container requires a supported macOS host",
            )

        if architecture not in {"arm64", "aarch64"}:
            return RuntimeProbeResult(
                state=RuntimeProbeState.UNAVAILABLE,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=None,
                system_status=None,
                reason="Apple Container integration requires Apple Silicon",
            )

        container_cli = shutil.which("container")
        if container_cli is None:
            return RuntimeProbeResult(
                state=RuntimeProbeState.UNAVAILABLE,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=None,
                system_status=None,
                reason="container CLI was not found on PATH",
            )

        try:
            result = self._runner.run(
                ("container", "system", "status", "--format", "json"),
                cwd=self._cwd,
                environment=self._environment,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception as exc:
            return RuntimeProbeResult(
                state=RuntimeProbeState.DEGRADED,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=container_cli,
                system_status=None,
                reason=f"container system status failed: {exc}",
            )

        if result.returncode != 0:
            return RuntimeProbeResult(
                state=RuntimeProbeState.DEGRADED,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=container_cli,
                system_status=None,
                reason="Apple Container system is not ready",
            )

        try:
            import json

            payload = json.loads(result.stdout.decode("utf-8"))
        except Exception as exc:
            return RuntimeProbeResult(
                state=RuntimeProbeState.DEGRADED,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=container_cli,
                system_status=None,
                reason=f"container system status was not valid JSON: {exc}",
            )

        if isinstance(payload, dict):
            status = str(payload.get("status", "")).lower()
            if status and status not in {"running", "ready", "healthy", "ok"}:
                return RuntimeProbeResult(
                    state=RuntimeProbeState.DEGRADED,
                    operating_system=operating_system,
                    architecture=architecture,
                    container_cli=container_cli,
                    system_status=payload,
                    reason=f"Apple Container system reports status {status!r}",
                )
            return RuntimeProbeResult(
                state=RuntimeProbeState.AVAILABLE,
                operating_system=operating_system,
                architecture=architecture,
                container_cli=container_cli,
                system_status=payload,
                reason="Apple Container runtime is ready",
            )

        return RuntimeProbeResult(
            state=RuntimeProbeState.DEGRADED,
            operating_system=operating_system,
            architecture=architecture,
            container_cli=container_cli,
            system_status=None,
            reason="container system status returned an unexpected JSON shape",
        )
