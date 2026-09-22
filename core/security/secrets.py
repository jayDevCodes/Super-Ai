from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping


class SecretBoundaryError(ValueError):
    """Raised when a runtime environment violates the secret boundary."""


SENSITIVE_NAME_HINTS = (
    "TOKEN",
    "PASSWORD",
    "PASS",
    "SECRET",
    "PRIVATE_KEY",
    "API_KEY",
    "AUTH",
    "CREDENTIAL",
)


_SAFE_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_sensitive_name(name: str) -> bool:
    """Return whether an environment variable name is treated as secret-bearing."""
    upper = name.upper()
    return any(hint in upper for hint in SENSITIVE_NAME_HINTS)


@dataclass(frozen=True, slots=True)
class SecretBoundaryPolicy:
    """Bound the environment surface exposed to sandbox and host-runtime commands."""

    max_variables: int = 64
    max_name_bytes: int = 255
    max_value_bytes: int = 4096
    max_total_value_bytes: int = 64 * 1024

    def validate(self) -> None:
        if self.max_variables <= 0:
            raise ValueError("max_variables must be > 0")
        if self.max_name_bytes <= 0:
            raise ValueError("max_name_bytes must be > 0")
        if self.max_value_bytes <= 0:
            raise ValueError("max_value_bytes must be > 0")
        if self.max_total_value_bytes <= 0:
            raise ValueError("max_total_value_bytes must be > 0")
        if self.max_value_bytes > self.max_total_value_bytes:
            raise ValueError("max_value_bytes must be <= max_total_value_bytes")


@dataclass(frozen=True, slots=True)
class SecretBoundaryEvidence:
    """Non-secret audit evidence for one environment boundary evaluation."""

    accepted: bool
    variable_count: int
    total_value_bytes: int
    finding_count: int
    sensitive_name_count: int
    invalid_name_count: int
    invalid_value_count: int
    oversized_value_count: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class SecretScan:
    """Non-secret findings from one environment boundary inspection."""

    safe: bool
    variable_count: int
    total_value_bytes: int
    sensitive_names: tuple[str, ...] = ()
    invalid_names: tuple[str, ...] = ()
    oversized_names: tuple[str, ...] = ()
    invalid_values: tuple[str, ...] = ()
    oversized_values: tuple[str, ...] = ()
    too_many_variables: bool = False
    total_value_limit_exceeded: bool = False

    @property
    def findings(self) -> tuple[str, ...]:
        findings: list[str] = []
        findings.extend(f"sensitive variable: {name}" for name in self.sensitive_names)
        findings.extend(f"invalid variable name: {name}" for name in self.invalid_names)
        findings.extend(f"variable name too long: {name}" for name in self.oversized_names)
        findings.extend(f"invalid variable value: {name}" for name in self.invalid_values)
        findings.extend(f"variable value too long: {name}" for name in self.oversized_values)
        if self.too_many_variables:
            findings.append("environment variable count exceeds policy")
        if self.total_value_limit_exceeded:
            findings.append("environment variable total size exceeds policy")
        return tuple(findings)


class SecretBoundaryScanner:
    """Fail-closed, secret-value-blind validation for sandbox environments."""

    def __init__(self, policy: SecretBoundaryPolicy | None = None) -> None:
        self._policy = policy or SecretBoundaryPolicy()
        self._policy.validate()

    @property
    def policy(self) -> SecretBoundaryPolicy:
        return self._policy

    def scan(self, environment: Mapping[str, str]) -> SecretScan:
        variable_count = len(environment)
        too_many_variables = variable_count > self._policy.max_variables
        total_value_bytes = 0
        sensitive_names: list[str] = []
        invalid_names: list[str] = []
        oversized_names: list[str] = []
        invalid_values: list[str] = []
        oversized_values: list[str] = []

        for raw_name, raw_value in environment.items():
            if not isinstance(raw_name, str):
                invalid_names.append("<non-string-key>")
                continue
            if not _SAFE_ENV_NAME_RE.fullmatch(raw_name):
                invalid_names.append(raw_name)
                continue

            name_bytes = len(raw_name.encode("utf-8"))
            if name_bytes > self._policy.max_name_bytes:
                oversized_names.append(raw_name)

            if is_sensitive_name(raw_name):
                sensitive_names.append(raw_name)

            if not isinstance(raw_value, str):
                invalid_values.append(raw_name)
                continue

            value_bytes = len(raw_value.encode("utf-8"))
            total_value_bytes += value_bytes

            if value_bytes > self._policy.max_value_bytes:
                oversized_values.append(raw_name)

            if any(char in raw_value for char in "\x00\r\n"):
                invalid_values.append(raw_name)

        total_value_limit_exceeded = (
            total_value_bytes > self._policy.max_total_value_bytes
        )

        safe = not (
            too_many_variables
            or total_value_limit_exceeded
            or sensitive_names
            or invalid_names
            or oversized_names
            or invalid_values
            or oversized_values
        )
        return SecretScan(
            safe=safe,
            variable_count=variable_count,
            total_value_bytes=total_value_bytes,
            sensitive_names=tuple(sorted(set(sensitive_names))),
            invalid_names=tuple(sorted(set(invalid_names))),
            oversized_names=tuple(sorted(set(oversized_names))),
            invalid_values=tuple(sorted(set(invalid_values))),
            oversized_values=tuple(sorted(set(oversized_values))),
            too_many_variables=too_many_variables,
            total_value_limit_exceeded=total_value_limit_exceeded,
        )

    def evidence(self, environment: Mapping[str, str]) -> SecretBoundaryEvidence:
        scan = self.scan(environment)
        material = {
            "accepted": scan.safe,
            "variable_count": scan.variable_count,
            "total_value_bytes": scan.total_value_bytes,
            "finding_count": len(scan.findings),
            "sensitive_name_count": len(scan.sensitive_names),
            "invalid_name_count": len(scan.invalid_names),
            "invalid_value_count": len(scan.invalid_values),
            "oversized_value_count": len(scan.oversized_values),
            "policy": {
                "max_variables": self._policy.max_variables,
                "max_name_bytes": self._policy.max_name_bytes,
                "max_value_bytes": self._policy.max_value_bytes,
                "max_total_value_bytes": self._policy.max_total_value_bytes,
            },
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                material,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return SecretBoundaryEvidence(
            accepted=scan.safe,
            variable_count=scan.variable_count,
            total_value_bytes=scan.total_value_bytes,
            finding_count=len(scan.findings),
            sensitive_name_count=len(scan.sensitive_names),
            invalid_name_count=len(scan.invalid_names),
            invalid_value_count=len(scan.invalid_values),
            oversized_value_count=len(scan.oversized_values),
            fingerprint=fingerprint,
        )

    def sanitize(self, environment: Mapping[str, str]) -> dict[str, str]:
        scan = self.scan(environment)
        if not scan.safe:
            detail = "; ".join(scan.findings)
            raise SecretBoundaryError(
                "sandbox environment violates secret boundary"
                + (f": {detail}" if detail else "")
            )
        return dict(environment)
