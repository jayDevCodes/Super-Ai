from __future__ import annotations

from dataclasses import dataclass, field
import re
from urllib.parse import urlparse


class SupplyChainValidationError(ValueError):
    pass


_SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _clean(value: str, field_name: str, max_len: int = 1024) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise SupplyChainValidationError(f"{field_name} must be a non-empty trimmed string")
    if len(value) > max_len or any(c in value for c in "\x00\r\n"):
        raise SupplyChainValidationError(f"{field_name} contains unsafe or oversized data")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    repository_url: str
    commit: str
    digest: str

    def validate(self) -> None:
        parsed = urlparse(self.repository_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or not parsed.path.strip("/")
            or parsed.query
            or parsed.fragment
        ):
            raise SupplyChainValidationError("repository_url must be a clean GitHub HTTPS URL")
        if not _SHA1.fullmatch(self.commit):
            raise SupplyChainValidationError("commit must be a 40-character Git SHA")
        if not _SHA256.fullmatch(self.digest):
            raise SupplyChainValidationError("digest must be a 64-character SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    key_id: str
    algorithm: str
    value: str

    def validate(self) -> None:
        _clean(self.key_id, "key_id", 256)
        if self.algorithm not in {"ed25519", "ecdsa-sha256"}:
            raise SupplyChainValidationError("unsupported signature algorithm")
        _clean(self.value, "signature", 16384)


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    builder_id: str
    source_commit: str
    build_type: str
    materials: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        _clean(self.builder_id, "builder_id", 256)
        if not _SHA1.fullmatch(self.source_commit):
            raise SupplyChainValidationError("source_commit must be a Git SHA")
        _clean(self.build_type, "build_type", 256)
        if len(self.materials) > 512:
            raise SupplyChainValidationError("materials list is too large")
        for item in self.materials:
            _clean(item, "material", 512)


@dataclass(frozen=True, slots=True)
class SbomSummary:
    package_count: int
    direct_dependencies: tuple[str, ...] = field(default_factory=tuple)
    known_vulnerabilities: int = 0
    critical_vulnerabilities: int = 0

    def validate(self) -> None:
        for name in ("package_count", "known_vulnerabilities", "critical_vulnerabilities"):
            if getattr(self, name) < 0:
                raise SupplyChainValidationError(f"{name} cannot be negative")
        if self.critical_vulnerabilities > self.known_vulnerabilities:
            raise SupplyChainValidationError("critical vulnerabilities cannot exceed total vulnerabilities")
        if self.package_count > 100_000:
            raise SupplyChainValidationError("SBOM package count exceeds bound")
        if len(self.direct_dependencies) > self.package_count:
            raise SupplyChainValidationError("direct dependency count exceeds package count")


@dataclass(frozen=True, slots=True)
class DependencyLock:
    entries: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        seen: set[str] = set()
        for package, digest in self.entries:
            _clean(package, "package", 256)
            if package in seen:
                raise SupplyChainValidationError(f"duplicate dependency: {package}")
            seen.add(package)
            if not _SHA256.fullmatch(digest):
                raise SupplyChainValidationError(f"dependency digest for {package} is invalid")

    def as_dict(self) -> dict[str, str]:
        self.validate()
        return {k: v for k, v in self.entries}


@dataclass(frozen=True, slots=True)
class RevocationEntry:
    subject: str
    reason: str
    expires_at_epoch: int | None = None

    def validate(self) -> None:
        _clean(self.subject, "subject", 512)
        _clean(self.reason, "reason", 1024)
        if self.expires_at_epoch is not None and self.expires_at_epoch <= 0:
            raise SupplyChainValidationError("expires_at_epoch must be positive")


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    identity: ArtifactIdentity
    signature: SignatureEnvelope | None = None
    provenance: ProvenanceRecord | None = None
    sbom: SbomSummary | None = None
    dependency_lock: DependencyLock | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def validate(self) -> None:
        self.identity.validate()
        if self.signature is not None:
            self.signature.validate()
        if self.provenance is not None:
            self.provenance.validate()
        if self.sbom is not None:
            self.sbom.validate()
        if self.dependency_lock is not None:
            self.dependency_lock.validate()
        if len(self.metadata) > 128:
            raise SupplyChainValidationError("metadata is too large")
        for key, value in self.metadata:
            _clean(key, "metadata key", 128)
            _clean(value, "metadata value", 1024)
