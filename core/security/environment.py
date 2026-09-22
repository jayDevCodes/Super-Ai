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

    for key, value in (explicit or {}).items():
        if not isinstance(key, str) or not key:
            raise EnvironmentPolicyError(
                "environment variable names must be non-empty strings"
            )
        if not isinstance(value, str):
            raise EnvironmentPolicyError(
                f"environment variable {key!r} value must be a string"
            )
        result[key] = value

    try:
        return SecretBoundaryScanner(policy).sanitize(result)
    except SecretBoundaryError as exc:
        raise EnvironmentPolicyError(str(exc)) from exc
