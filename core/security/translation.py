from __future__ import annotations

from dataclasses import dataclass

from .posture import FilesystemMode, NetworkMode, SecurityProfile, SyscallMode


@dataclass(frozen=True, slots=True)
class ContainerSecurityEnvelope:
    run_as_non_root: bool
    no_new_privileges: bool
    readonly_rootfs: bool
    syscall_mode: str
    network_mode: str
    allowed_hosts: tuple[str, ...]
    allowed_cidrs: tuple[str, ...]
    allowed_writes: tuple[str, ...]
    max_processes: int
    max_open_files: int
    capabilities: tuple[str, ...]


def compile_security_envelope(profile: SecurityProfile) -> ContainerSecurityEnvelope:
    profile.validate()
    return ContainerSecurityEnvelope(
        run_as_non_root=profile.non_root,
        no_new_privileges=profile.no_new_privileges,
        readonly_rootfs=profile.filesystem.mode is FilesystemMode.READ_ONLY_ROOT,
        syscall_mode=profile.syscall_mode.value,
        network_mode=profile.network.mode.value,
        allowed_hosts=tuple(sorted(profile.network.allowed_hosts)),
        allowed_cidrs=tuple(sorted(profile.network.allowed_cidrs)),
        allowed_writes=tuple(sorted(profile.filesystem.allowed_writes)),
        max_processes=profile.process.max_processes,
        max_open_files=profile.process.max_open_files,
        capabilities=tuple(sorted(profile.capabilities)),
    )


def security_arguments(profile: SecurityProfile) -> tuple[str, ...]:
    """Generic, deterministic intent arguments for a runtime-specific adapter."""
    envelope = compile_security_envelope(profile)
    args = [
        "--non-root",
        "--no-new-privileges",
        f"--syscall-mode={envelope.syscall_mode}",
        f"--network={envelope.network_mode}",
        f"--max-processes={envelope.max_processes}",
        f"--max-open-files={envelope.max_open_files}",
    ]
    if envelope.readonly_rootfs:
        args.append("--read-only-root")
    for path in envelope.allowed_writes:
        args.append(f"--write-root={path}")
    for host in envelope.allowed_hosts:
        args.append(f"--allow-host={host}")
    for cidr in envelope.allowed_cidrs:
        args.append(f"--allow-cidr={cidr}")
    for capability in envelope.capabilities:
        args.append(f"--capability={capability}")
    return tuple(args)
