from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import ipaddress


class SecurityPostureError(ValueError):
    pass


class SyscallMode(str, Enum):
    DEFAULT = "default"
    RESTRICTED = "restricted"


class FilesystemMode(str, Enum):
    READ_ONLY_ROOT = "read-only-root"
    READ_WRITE_ROOT = "read-write-root"


class NetworkMode(str, Enum):
    DISABLED = "disabled"
    ALLOWLIST = "allowlist"


class SecretMode(str, Enum):
    NONE = "none"
    EXPLICIT_NON_SENSITIVE = "explicit-non-sensitive"


@dataclass(frozen=True, slots=True)
class ProcessQuota:
    max_processes: int = 64
    max_open_files: int = 1024

    def validate(self) -> None:
        if not 1 <= self.max_processes <= 4096:
            raise SecurityPostureError("max_processes out of range")
        if not 16 <= self.max_open_files <= 65536:
            raise SecurityPostureError("max_open_files out of range")


@dataclass(frozen=True, slots=True)
class FilesystemPosture:
    mode: FilesystemMode = FilesystemMode.READ_ONLY_ROOT
    allowed_writes: tuple[str, ...] = ("/workspace", "/tmp")

    def validate(self) -> None:
        if self.mode is FilesystemMode.READ_ONLY_ROOT and not self.allowed_writes:
            raise SecurityPostureError("read-only root posture still needs an explicit write scope")
        for path in self.allowed_writes:
            if not path.startswith("/") or any(c in path for c in "\x00\r\n"):
                raise SecurityPostureError("allowed write path must be an absolute safe path")
            parts = [p for p in path.split("/") if p]
            if ".." in parts:
                raise SecurityPostureError("path traversal is forbidden")


@dataclass(frozen=True, slots=True)
class NetworkEgress:
    mode: NetworkMode = NetworkMode.DISABLED
    allowed_hosts: tuple[str, ...] = ()
    allowed_cidrs: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.mode is NetworkMode.DISABLED and (self.allowed_hosts or self.allowed_cidrs):
            raise SecurityPostureError("disabled network mode cannot contain an allowlist")
        for host in self.allowed_hosts:
            if not host or any(c in host for c in "\x00\r\n /"):
                raise SecurityPostureError("invalid network hostname")
        for cidr in self.allowed_cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise SecurityPostureError("invalid network CIDR") from exc

    def permits_ip(self, address: str) -> bool:
        self.validate()
        if self.mode is NetworkMode.DISABLED:
            return False
        ip = ipaddress.ip_address(address)
        return any(ip in ipaddress.ip_network(c, strict=False) for c in self.allowed_cidrs)


@dataclass(frozen=True, slots=True)
class SecretBoundary:
    mode: SecretMode = SecretMode.NONE
    maximum_value_bytes: int = 4096
    forbidden_names: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.maximum_value_bytes <= 0 or self.maximum_value_bytes > 16384:
            raise SecurityPostureError("secret maximum value size out of range")
        for name in self.forbidden_names:
            if not name or any(c in name for c in "\x00\r\n="):
                raise SecurityPostureError("invalid secret variable name")


@dataclass(frozen=True, slots=True)
class SecurityProfile:
    non_root: bool = True
    no_new_privileges: bool = True
    capabilities: frozenset[str] = frozenset()
    syscall_mode: SyscallMode = SyscallMode.RESTRICTED
    filesystem: FilesystemPosture = FilesystemPosture()
    network: NetworkEgress = NetworkEgress()
    secrets: SecretBoundary = SecretBoundary()
    process: ProcessQuota = ProcessQuota()

    def validate(self) -> None:
        if not self.non_root:
            raise SecurityPostureError("non-root execution is mandatory")
        if not self.no_new_privileges:
            raise SecurityPostureError("no_new_privileges is mandatory")
        forbidden = {"SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE"}
        unexpected = forbidden.intersection(self.capabilities)
        if unexpected:
            raise SecurityPostureError(
                "forbidden Linux capability requested: " + ", ".join(sorted(unexpected))
            )
        self.filesystem.validate()
        self.network.validate()
        self.secrets.validate()
        self.process.validate()


@dataclass(frozen=True, slots=True)
class SecurityAuditReport:
    accepted: bool
    findings: tuple[str, ...]


class SecurityAuditor:
    def review(self, profile: SecurityProfile) -> SecurityAuditReport:
        findings: list[str] = []
        try:
            profile.validate()
        except ValueError as exc:
            findings.append(str(exc))
        if profile.network.mode is NetworkMode.DISABLED and (
            profile.network.allowed_hosts or profile.network.allowed_cidrs
        ):
            findings.append("network allowlist exists while network is disabled")
        if "ALL" in profile.capabilities or "CAP_SYS_ADMIN" in profile.capabilities:
            findings.append("wildcard or administrative capability is forbidden")
        return SecurityAuditReport(not findings, tuple(sorted(set(findings))))
