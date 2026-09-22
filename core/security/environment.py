from __future__ import annotations

import os
from typing import Mapping

from .secrets import (
    SecretBoundaryError,
    SecretBoundaryPolicy,
    SecretBoundaryScanner,
    is_sensitive_name,
)


class EnvironmentPolicyError(ValueError):
    """Raised when an execution environment violates the allowlist policy."""


def build_sandbox_environment(
    explicit: Mapping[str, str] | None = None,
    *,
    inherited_allowlist: tuple[str, ...] = ("PATH", "LANG", "LC_ALL"),
    policy: SecretBoundaryPolicy | None = None,
) -> dict[str, str]:
    """Build and validate a bounded environment instead of forwarding the host environment."""
    normalized_allowlist = tuple(inherited_allowlist)
    if len(set(normalized_allowlist)) != len(normalized_allowlist):
        raise EnvironmentPolicyError("inherited_allowlist must not contain duplicates")

    scanner = SecretBoundaryScanner(policy)
    result: dict[str, str] = {}

    for key in normalized_allowlist:
        if not isinstance(key, str) or not key:
            raise EnvironmentPolicyError(
                "inherited environment variable names must be non-empty strings"
            )
        if is_sensitive_name(key):
            raise EnvironmentPolicyError(
                f"sensitive variable {key!r} cannot be inherited"
            )
        value = os.environ.get(key)
        if value is not None:
            result[key] = value

    explicit_values = explicit or {}
    explicit_scan = scanner.scan(explicit_values)
    if not explicit_scan.safe:
        detail = "; ".join(explicit_scan.findings)
        raise EnvironmentPolicyError(
            "explicit environment violates secret boundary"
            + (f": {detail}" if detail else "")
        )

    for key, value in explicit_values.items():
        result[key] = value

    try:
        return scanner.sanitize(result)
    except SecretBoundaryError as exc:
        raise EnvironmentPolicyError(str(exc)) from exc
