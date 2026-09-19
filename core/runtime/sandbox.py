from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import re


class SandboxError(RuntimeError):
    """Raised when a sandbox policy cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """Execution restrictions that every sandbox backend must honor."""

    memory_mb: int
    cpu_threads: int
    max_processes: int = 64
    timeout_seconds: float = 60.0
    network: str = "disabled"
    network_name: str | None = None
    run_as_user: str | None = "65532:65532"
    root_filesystem_read_only: bool = True

    def validate(self) -> None:
        if self.memory_mb <= 0:
            raise ValueError("memory_mb must be > 0")
        if self.cpu_threads <= 0:
            raise ValueError("cpu_threads must be > 0")
        if self.max_processes <= 0:
            raise ValueError("max_processes must be > 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.network not in {"disabled", "isolated", "enabled"}:
            raise ValueError("network must be disabled, isolated, or enabled")
        if self.network == "disabled" and self.network_name is not None:
            raise ValueError(
                "network_name is only valid for isolated/enabled networks"
            )
        if self.network in {"isolated", "enabled"}:
            if not self.network_name or not _NETWORK_NAME_RE.fullmatch(
                self.network_name
            ):
                raise ValueError(
                    "network_name must be provided and contain only safe network characters"
                )
        if self.run_as_user is not None:
            if not _USER_RE.fullmatch(self.run_as_user):
                raise ValueError("run_as_user contains unsupported characters")

    @property
    def network_permitted(self) -> bool:
        return self.network != "disabled"


@dataclass(frozen=True, slots=True)
class SandboxPlan:
    """Immutable, non-shell execution plan produced before any process launch."""

    backend: str
    image: str
    command: tuple[str, ...]
    source_path: Path
    output_path: Path
    policy: SandboxPolicy
    execution_ready: bool
    safety_note: str = ""


class SandboxBackend(Protocol):
    """Planner boundary for isolated capability execution."""

    def build_plan(
        self,
        *,
        image: str,
        command: tuple[str, ...],
        source_path: Path,
        output_path: Path,
        policy: SandboxPolicy,
    ) -> SandboxPlan:
        ...


_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:-]{0,254}$")
_NETWORK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_USER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _validate_path(path: Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise SandboxError(f"{label} must be an existing directory")
    if resolved.is_symlink():
        raise SandboxError(f"{label} must not be a symlink")
    return resolved


def _validate_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if not command:
        raise SandboxError("command must not be empty")
    if any(not part for part in command):
        raise SandboxError("command arguments must be non-empty")
    return tuple(command)


class AppleContainerSandbox:
    """Build hardened Apple Container plans without executing them.

    The plan explicitly requests network=none for the default disabled-network
    posture. The executor independently validates this exact invariant before
    a container is started.
    """

    backend_name = "apple-container"

    def build_plan(
        self,
        *,
        image: str,
        command: tuple[str, ...],
        source_path: Path,
        output_path: Path,
        policy: SandboxPolicy,
    ) -> SandboxPlan:
        policy.validate()
        if not _IMAGE_RE.fullmatch(image):
            raise SandboxError("image contains unsupported characters")

        command = _validate_command(command)
        source = _validate_path(source_path, "source_path")
        output = _validate_path(output_path, "output_path")

        if source == output:
            raise SandboxError("source_path and output_path must be different")

        args = self._build_run_args(
            image=image,
            command=command,
            source=source,
            output=output,
            policy=policy,
        )

        if policy.network == "disabled":
            execution_ready = True
            note = (
                "Default network posture is disabled with explicit --network none; "
                "the Apple Container executor must verify this exact flag before start."
            )
        else:
            execution_ready = True
            note = "Network access is explicitly enabled by policy."

        return SandboxPlan(
            backend=self.backend_name,
            image=image,
            command=tuple([*args, image, *command]),
            source_path=source,
            output_path=output,
            policy=policy,
            execution_ready=execution_ready,
            safety_note=note,
        )

    def build_create_command(
        self,
        plan: SandboxPlan,
        *,
        container_id: str,
    ) -> tuple[str, ...]:
        """Translate a validated plan into an explicit container create command."""
        if plan.backend != self.backend_name:
            raise SandboxError(
                f"plan backend {plan.backend!r} is not {self.backend_name!r}"
            )
        if not container_id or not _CONTAINER_ID_RE.fullmatch(container_id):
            raise SandboxError("container_id contains unsupported characters")

        plan.policy.validate()
        if plan.source_path == plan.output_path:
            raise SandboxError("source_path and output_path must be different")

        inner_command = _extract_inner_command(plan)
        args = self._build_run_args(
            image=plan.image,
            command=inner_command,
            source=plan.source_path,
            output=plan.output_path,
            policy=plan.policy,
        )

        args[1] = "create"
        args.insert(2, "--name")
        args.insert(3, container_id)
        return tuple([*args, plan.image, *inner_command])

    @staticmethod
    def _build_run_args(
        *,
        image: str,
        command: tuple[str, ...],
        source: Path,
        output: Path,
        policy: SandboxPolicy,
    ) -> list[str]:
        args: list[str] = [
            "container",
            "run",
            "--read-only",
            "--init",
            "--cap-drop",
            "ALL",
            "--cpus",
            str(policy.cpu_threads),
            "--memory",
            f"{policy.memory_mb}M",
            "--ulimit",
            f"nproc={policy.max_processes}:{policy.max_processes}",
            "--mount",
            f"type=bind,source={source},target=/capability,readonly",
            "--mount",
            f"type=bind,source={output},target=/workspace",
            "--workdir",
            "/workspace",
        ]

        if policy.root_filesystem_read_only is False:
            raise SandboxError(
                "AppleContainerSandbox requires root_filesystem_read_only=True"
            )

        if policy.run_as_user is not None:
            args.extend(["--user", policy.run_as_user])

        if policy.network == "disabled":
            args.extend(["--network", "none", "--no-dns"])
        else:
            args.extend(["--network", policy.network_name or ""])

        return args


_CONTAINER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


def _extract_inner_command(plan: SandboxPlan) -> tuple[str, ...]:
    """Recover the intended in-container argv from an Apple Container plan."""
    try:
        image_index = plan.command.index(plan.image)
    except ValueError as exc:
        raise SandboxError("sandbox plan does not contain its declared image") from exc

    command = plan.command[image_index + 1 :]
    return _validate_command(tuple(command))
