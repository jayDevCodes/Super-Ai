from __future__ import annotations

from dataclasses import dataclass

from .models import ArtifactRecord, RevocationEntry


@dataclass(frozen=True, slots=True)
class TrustPolicy:
    require_signature: bool = True
    require_provenance: bool = True
    require_sbom: bool = True
    require_dependency_lock: bool = True
    max_known_vulnerabilities: int = 10
    max_critical_vulnerabilities: int = 0
    minimum_trust_score: int = 80

    def validate(self) -> None:
        if self.max_known_vulnerabilities < 0 or self.max_critical_vulnerabilities < 0:
            raise ValueError("vulnerability ceilings cannot be negative")
        if not 0 <= self.minimum_trust_score <= 100:
            raise ValueError("minimum_trust_score must be in [0, 100]")


@dataclass(frozen=True, slots=True)
class TrustDecision:
    accepted: bool
    score: int
    reasons: tuple[str, ...]


class TrustScorer:
    """Deterministic evidence score; it is not a security guarantee."""

    @staticmethod
    def score(record: ArtifactRecord) -> int:
        record.validate()
        score = 0
        score += 30 if record.signature else 0
        score += 25 if record.provenance else 0
        score += 25 if record.sbom else 0
        score += 20 if record.dependency_lock else 0
        if record.sbom and record.sbom.known_vulnerabilities:
            score -= min(20, record.sbom.known_vulnerabilities)
        if record.sbom and record.sbom.critical_vulnerabilities:
            score -= min(30, record.sbom.critical_vulnerabilities * 10)
        return max(0, min(100, score))


class ArtifactAdmissionPolicy:
    def __init__(
        self,
        policy: TrustPolicy | None = None,
        revocations: tuple[RevocationEntry, ...] = (),
    ) -> None:
        self.policy = policy or TrustPolicy()
        self.policy.validate()
        self.revocations = revocations
        for item in revocations:
            item.validate()

    def evaluate(self, record: ArtifactRecord) -> TrustDecision:
        reasons: list[str] = []
        try:
            record.validate()
        except ValueError as exc:
            return TrustDecision(False, 0, (str(exc),))

        subject = record.identity.repository_url + "@" + record.identity.commit
        if any(item.subject == subject for item in self.revocations):
            reasons.append("artifact identity is revoked")
        if self.policy.require_signature and record.signature is None:
            reasons.append("signature evidence is required")
        if self.policy.require_provenance and record.provenance is None:
            reasons.append("provenance evidence is required")
        if self.policy.require_sbom and record.sbom is None:
            reasons.append("SBOM evidence is required")
        if self.policy.require_dependency_lock and record.dependency_lock is None:
            reasons.append("dependency lock evidence is required")

        if record.sbom:
            if record.sbom.known_vulnerabilities > self.policy.max_known_vulnerabilities:
                reasons.append("known vulnerability ceiling exceeded")
            if record.sbom.critical_vulnerabilities > self.policy.max_critical_vulnerabilities:
                reasons.append("critical vulnerability ceiling exceeded")

        score = TrustScorer.score(record)
        if score < self.policy.minimum_trust_score:
            reasons.append("trust score is below policy minimum")
        return TrustDecision(not reasons, score, tuple(reasons))
