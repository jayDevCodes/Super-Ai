from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .manifest import CapabilityManifest, ManifestValidationError


class ResolutionError(RuntimeError):
    """Raised when a capability source cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class SourcePlan:
    """Immutable execution plan for fetching exactly one pinned Git revision."""

    capability_id: str
    repository_url: str
    pinned_commit: str
    archive_url: str
    clone_url: str
    subdirectory: str
    partial_clone_command: tuple[str, ...]
    sparse_checkout_command: tuple[str, ...]

    @property
    def effective_path(self) -> str:
        return self.subdirectory or "."

    @property
    def has_sparse_target(self) -> bool:
        return bool(self.subdirectory)


class GitHubSourceResolver:
    """Resolve a validated manifest into a deterministic, immutable source plan.

    This component creates a plan; it does not download or execute source.
    Downloading, checksum verification, sandboxing, and execution belong to
    later runtime boundaries.
    """

    def resolve(self, manifest: CapabilityManifest) -> SourcePlan:
        try:
            manifest.validate()
        except ManifestValidationError as exc:
            raise ResolutionError("manifest validation failed") from exc

        parsed = urlparse(manifest.artifact.repository_url)
        owner_repo = parsed.path.strip("/")
        if owner_repo.endswith(".git"):
            owner_repo = owner_repo[:-4]

        parts = owner_repo.split("/")
        if len(parts) != 2 or any(not part for part in parts):
            raise ResolutionError(
                "repository_url must resolve to exactly github.com/owner/repo"
            )

        owner, repo = parts
        pinned = manifest.artifact.pinned_commit

        archive_url = (
            f"https://github.com/{owner}/{repo}/archive/{pinned}.tar.gz"
        )
        clone_url = f"https://github.com/{owner}/{repo}.git"

        return SourcePlan(
            capability_id=manifest.capability_id,
            repository_url=manifest.artifact.repository_url,
            pinned_commit=pinned,
            archive_url=archive_url,
            clone_url=clone_url,
            subdirectory=manifest.artifact.subdirectory,
            partial_clone_command=(
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                "--depth=1",
                "--revision",
                pinned,
                clone_url,
            ),
            sparse_checkout_command=(
                "git",
                "sparse-checkout",
                "set",
                "--cone",
                manifest.artifact.subdirectory or ".",
            ),
        )
