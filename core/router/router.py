from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from core.contracts import TaskConstraints
from core.policy import CapabilityPolicyEngine, PolicyDecisionState
from registry.catalog import CapabilityRegistry, RegistryEntry


class RoutingError(RuntimeError):
    """Raised when a capability cannot be selected safely."""


@dataclass(frozen=True, slots=True)
class RouteRequest:
    """Semantic and policy requirements for one capability selection."""

    goal: str
    capability_id: str | None = None
    required_permissions: frozenset[str] = frozenset()
    task_constraints: TaskConstraints | None = None

    def validate(self) -> None:
        if not self.goal or not self.goal.strip():
            raise ValueError("goal must be non-empty")
        if self.capability_id is not None and not self.capability_id.strip():
            raise ValueError("capability_id must be non-empty when provided")
        if any(not permission.strip() for permission in self.required_permissions):
            raise ValueError("required_permissions must contain non-empty strings")
        if self.task_constraints is not None:
            self.task_constraints.validate()


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A deterministic routing candidate plus its policy decision and score."""

    entry: RegistryEntry
    score: int
    reasons: tuple[str, ...]
    policy_state: PolicyDecisionState
    policy_reasons: tuple[str, ...]


class CapabilityRouter:
    """Select capabilities deterministically from the validated registry."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy_engine: CapabilityPolicyEngine,
    ) -> None:
        self._registry = registry
        self._policy_engine = policy_engine

    def route(
        self,
        request: RouteRequest,
        *,
        include_confirmation: bool = False,
    ) -> tuple[RouteCandidate, ...]:
        request.validate()
        candidates: list[RouteCandidate] = []

        required = set(request.required_permissions)
        requested_tokens = _tokens(request.goal)

        for entry in self._registry.all():
            permissions = set(entry.spec.permissions)
            if not required.issubset(permissions):
                continue

            decision = self._policy_engine.evaluate(
                entry.spec,
                request.task_constraints,
            )
            if decision.state is PolicyDecisionState.DENY:
                continue
            if (
                decision.state is PolicyDecisionState.CONFIRM
                and not include_confirmation
            ):
                continue

            score, reasons = self._score(
                entry,
                request,
                requested_tokens=requested_tokens,
            )
            if score <= 0 and request.capability_id is None:
                continue

            candidates.append(
                RouteCandidate(
                    entry=entry,
                    score=score,
                    reasons=tuple(reasons),
                    policy_state=decision.state,
                    policy_reasons=decision.reasons,
                )
            )

        if not candidates:
            raise RoutingError("no policy-compatible capability matched the request")

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.entry.manifest.capability_id,
                candidate.entry.manifest.version,
            )
        )
        return tuple(candidates)

    def select(
        self,
        request: RouteRequest,
        *,
        include_confirmation: bool = False,
    ) -> RouteCandidate:
        candidates = self.route(
            request,
            include_confirmation=include_confirmation,
        )
        return candidates[0]

    @staticmethod
    def _score(
        entry: RegistryEntry,
        request: RouteRequest,
        *,
        requested_tokens: set[str],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        if request.capability_id is not None:
            if entry.manifest.capability_id == request.capability_id:
                score += 1000
                reasons.append("exact capability_id match")
            else:
                return 0, []

        candidate_tokens = _tokens(
            " ".join(
                (
                    entry.manifest.capability_id,
                    entry.manifest.description,
                    entry.spec.description,
                    *entry.spec.permissions,
                )
            )
        )
        overlap = requested_tokens & candidate_tokens
        if overlap:
            score += 10 * len(overlap)
            reasons.append(f"{len(overlap)} semantic token matches")

        permission_bonus = len(request.required_permissions & set(entry.spec.permissions))
        if permission_bonus:
            score += 5 * permission_bonus
            reasons.append(f"{permission_bonus} required permissions satisfied")

        return score, reasons


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))
