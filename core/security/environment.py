from __future__ import annotations

import os
from typing import Mapping


class EnvironmentPolicyError(ValueError):
    """Raised when an execution environment violates the allowlist policy."""


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


def is_sensitive_name(name: str) -> bool:
    upper = name.upper()
    return any(hint in upper for hint in SENSITIVE_NAME_HINTS)


def build_sandbox_environment(
    explicit: Mapping[str, str] | None = None,
    *,
    inherited_allowlist: tuple[str, ...] = ("PATH", "LANG", "LC_ALL"),
) -> dict[str, str]:
    """Build an explicit environment instead of forwarding the host environment."""
    result: dict[str, str] = {}
    for key in inherited_allowlist:
        if is_sensitive_name(key):
            raise EnvironmentPolicyError(
                f"sensitive variable {key!r} cannot be inherited"
            )
        value = os.environ.get(key)
        if value is not None:
            result[key] = value

    for key, value in (explicit or {}).items():
        if not key or "=" in key or "\x00" in key or "\r" in key or "\n" in key:
            raise EnvironmentPolicyError("environment variable names must be safe")
        if is_sensitive_name(key):
            raise EnvironmentPolicyError(
                f"sensitive environment variable {key!r} is not allowed"
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            raise EnvironmentPolicyError(
                f"environment variable {key!r} contains unsafe control characters"
            )
        if len(value.encode("utf-8")) > 4096:
            raise EnvironmentPolicyError(
                f"environment variable {key!r} exceeds 4096-byte limit"
            )
        result[key] = value
    return result
