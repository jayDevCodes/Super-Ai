from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.contracts import CapabilitySpec, TaskConstraints


class PolicyDecisionState(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    """Explicit allowlist and resource ceiling for capability execution."""

    allowed_permissions: frozenset[str] = frozenset()
    max_ram_mb: int = 4096
    max_cpu_threads: int = 4
    network_enabled: bool = True

    def validate(self) -> None:
        if self.max_ram_mb <= 0:
            raise ValueError("max_ram_mb must be > 0")
        if self.max_cpu_threads <= 0:
            raise ValueError("max_cpu_threads must be > 0")
        if any(not permission.strip() for permission in self.allowed_permissions):
            raise ValueError("allowed_permissions must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    state: PolicyDecisionState
    reasons: tuple[str, ...]
    network: str


class CapabilityPolicyEngine:
    """Evaluate capability permissions with deny-by-default semantics."""

    def __init__(self, policy: CapabilityPolicy | None = None) -> None:
        self._policy = policy or CapabilityPolicy()
        self._policy.validate()

    def evaluate(
        self,
        capability: CapabilitySpec,
        task: TaskConstraints | None = None,
    ) -> PolicyDecision:
        capability.validate()
        if task is not None:
            task.validate()

        reasons: list[str] = []
        unknown = sorted(
            set(capability.permissions) - set(self._policy.allowed_permissions)
        )
        if unknown:
            reasons.append("permissions not allowlisted: " + ", ".join(unknown))
            return PolicyDecision(
                state=PolicyDecisionState.DENY,
                reasons=tuple(reasons),
                network="disabled",
            )

        if capability.resource.ram_hard_mb > self._policy.max_ram_mb:
            reasons.append("capability exceeds policy RAM ceiling")
        if capability.resource.cpu_threads > self._policy.max_cpu_threads:
            reasons.append("capability exceeds policy CPU ceiling")

        if reasons:
            return PolicyDecision(
                state=PolicyDecisionState.DENY,
                reasons=tuple(reasons),
                network="disabled",
            )

        task_allows_network = bool(task and task.allow_network)
        requests_network = "network" in capability.permissions
        network = (
            "enabled"
            if self._policy.network_enabled
            and task_allows_network
            and requests_network
            else "disabled"
        )

        if requests_network and network == "disabled":
            reasons.append(
                "network permission is present but task/network policy does not permit it"
            )
            return PolicyDecision(
                state=PolicyDecisionState.DENY,
                reasons=tuple(reasons),
                network="disabled",
            )

        consequential = {
            "external-action",
            "consequential-action",
            "submit",
        }
        if (
            consequential.intersection(capability.permissions)
            and task is not None
            and task.require_confirmation_for_consequential_actions
        ):
            reasons.append("consequential action requires human confirmation")
            return PolicyDecision(
                state=PolicyDecisionState.CONFIRM,
                reasons=tuple(reasons),
                network=network,
            )

        return PolicyDecision(
            state=PolicyDecisionState.ALLOW,
            reasons=tuple(reasons),
            network=network,
        )
