from __future__ import annotations

from dataclasses import dataclass

from core.controlplane.specs import RuntimeSpecGuardian, RuntimeSpecReview
from core.security.hardening import HardeningController, HardeningEvidence
from core.security.posture import NetworkEgress, NetworkMode, ProcessQuota, SecurityProfile
from core.supplychain.models import ArtifactRecord
from core.supplychain.policy import ArtifactAdmissionPolicy, TrustDecision
from registry.runtime import RuntimeSpec


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    accepted: bool
    reasons: tuple[str, ...]
    runtime: RuntimeSpecReview | None
    supply_chain: TrustDecision | None
    security: HardeningEvidence

    @property
    def evidence_fingerprints(self) -> tuple[str, ...]:
        values: list[str] = [self.security.profile_fingerprint]
        if self.runtime is not None:
            values.append(self.runtime.fingerprint)
        if self.supply_chain is not None:
            values.append(f"trust:{self.supply_chain.score}")
        return tuple(values)


class ExecutionAdmissionGate:
    """Compose independent runtime, security, and optional supply-chain gates."""

    def __init__(
        self,
        *,
        runtime_guardian: RuntimeSpecGuardian | None = None,
        supply_chain_policy: ArtifactAdmissionPolicy | None = None,
        hardening_controller: HardeningController | None = None,
    ) -> None:
        self.runtime_guardian = runtime_guardian or RuntimeSpecGuardian()
        self.supply_chain_policy = supply_chain_policy or ArtifactAdmissionPolicy()
        self.hardening_controller = hardening_controller or HardeningController()

    def evaluate(
        self,
        spec: RuntimeSpec,
        *,
        security_profile: SecurityProfile | None = None,
        artifact: ArtifactRecord | None = None,
        require_artifact: bool = False,
    ) -> AdmissionDecision:
        runtime = self.runtime_guardian.review(spec)
        profile = security_profile or SecurityProfile()
        security = self.hardening_controller.review(profile)

        supply = None
        reasons = list(runtime.issues) + list(security.findings)
        if require_artifact and artifact is None:
            reasons.append("external artifact evidence is required")
        elif artifact is not None:
            supply = self.supply_chain_policy.evaluate(artifact)
            reasons.extend(supply.reasons)

        return AdmissionDecision(
            accepted=not reasons,
            reasons=tuple(sorted(set(reasons))),
            runtime=runtime,
            supply_chain=supply,
            security=security,
        )

    @staticmethod
    def profile_for(
        *,
        max_processes: int,
        network_enabled: bool = False,
    ) -> SecurityProfile:
        profile = SecurityProfile(
            network=NetworkEgress(
                mode=NetworkMode.ALLOWLIST if network_enabled else NetworkMode.DISABLED
            ),
            process=ProcessQuota(max_processes=max_processes),
        )
        profile.validate()
        return profile
