from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

_SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ManifestValidationError(ValueError):
    """Raised when a capability manifest violates the registry contract."""


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Immutable source identity for a dynamically loaded capability."""

    repository_url: str
    pinned_commit: str
    sha256: str | None = None
    subdirectory: str = ""

    def validate(self) -> None:
        parsed = urlparse(self.repository_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or not parsed.path.strip("/")
            or parsed.query
            or parsed.fragment
        ):
            raise ManifestValidationError(
                "repository_url must be a clean https://github.com/owner/repo URL"
            )
        if not _SHA1_RE.fullmatch(self.pinned_commit):
            raise ManifestValidationError(
                "pinned_commit must be a 40-character hexadecimal Git commit SHA"
            )
        if self.sha256 is not None and not _SHA256_RE.fullmatch(self.sha256):
            raise ManifestValidationError(
                "sha256 must be a 64-character hexadecimal digest"
            )
        if self.subdirectory.startswith("/") or ".." in self.subdirectory.split("/"):
            raise ManifestValidationError(
                "subdirectory must stay within the repository root"
            )


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    """Registry entry required before a capability can be loaded."""

    capability_id: str
    version: str
    artifact: ArtifactSpec
    description: str = ""

    def validate(self) -> None:
        if not self.capability_id or self.capability_id.strip() != self.capability_id:
            raise ManifestValidationError(
                "capability_id must be a non-empty trimmed string"
            )
        if not self.version or self.version.strip() != self.version:
            raise ManifestValidationError("version must be a non-empty trimmed string")
        if not self.description.strip():
            raise ManifestValidationError("description must be non-empty")
        self.artifact.validate()
