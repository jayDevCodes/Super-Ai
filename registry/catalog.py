from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.contracts import CapabilitySpec, ResourceContract
from .manifest import ArtifactSpec, CapabilityManifest


class RegistryError(RuntimeError):
    """Raised when the capability registry contains invalid or ambiguous data."""


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """Validated registry record combining executable metadata and source identity."""

    manifest: CapabilityManifest
    spec: CapabilitySpec

    def validate(self) -> None:
        self.manifest.validate()
        self.spec.validate()
        if self.manifest.capability_id != self.spec.capability_id:
            raise RegistryError("manifest/spec capability_id mismatch")
        if self.manifest.version != self.spec.version:
            raise RegistryError("manifest/spec version mismatch")


class CapabilityRegistry:
    """Deterministic in-memory capability registry with optional JSON persistence."""

    def __init__(self, entries: Iterable[RegistryEntry] = ()) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: RegistryEntry) -> None:
        entry.validate()
        key = self._key(entry.manifest.capability_id, entry.manifest.version)
        if key in self._entries:
            raise RegistryError(f"duplicate capability/version: {key}")
        self._entries[key] = entry

    def get(self, capability_id: str, version: str | None = None) -> RegistryEntry:
        if version is not None:
            key = self._key(capability_id, version)
            try:
                return self._entries[key]
            except KeyError as exc:
                raise RegistryError(f"capability not found: {key}") from exc

        matches = [
            entry for entry in self._entries.values()
            if entry.manifest.capability_id == capability_id
        ]
        if not matches:
            raise RegistryError(f"capability not found: {capability_id}")
        if len(matches) != 1:
            versions = ", ".join(
                sorted(entry.manifest.version for entry in matches)
            )
            raise RegistryError(
                f"version required for ambiguous capability {capability_id!r}: {versions}"
            )
        return matches[0]

    def search(
        self,
        *,
        permission: str | None = None,
        text: str | None = None,
    ) -> tuple[RegistryEntry, ...]:
        normalized_text = text.strip().lower() if text is not None else None
        matches = []
        for entry in self._entries.values():
            if permission is not None and permission not in entry.spec.permissions:
                continue
            if normalized_text:
                haystack = " ".join(
                    (
                        entry.manifest.capability_id,
                        entry.manifest.version,
                        entry.manifest.description,
                        entry.spec.description,
                        *sorted(entry.spec.permissions),
                    )
                ).lower()
                if normalized_text not in haystack:
                    continue
            matches.append(entry)
        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.manifest.capability_id,
                    item.manifest.version,
                ),
            )
        )

    def all(self) -> tuple[RegistryEntry, ...]:
        return tuple(
            sorted(
                self._entries.values(),
                key=lambda item: (
                    item.manifest.capability_id,
                    item.manifest.version,
                ),
            )
        )

    @classmethod
    def from_json(cls, path: Path) -> "CapabilityRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RegistryError("registry JSON root must be an object")
        raw_entries = payload.get("capabilities")
        if not isinstance(raw_entries, list):
            raise RegistryError("registry JSON must contain a capabilities array")

        registry = cls()
        for raw in raw_entries:
            registry.register(_entry_from_json(raw))
        return registry

    @staticmethod
    def _key(capability_id: str, version: str) -> str:
        return f"{capability_id}@{version}"


def _entry_from_json(raw: Any) -> RegistryEntry:
    if not isinstance(raw, Mapping):
        raise RegistryError("registry entry must be an object")

    manifest_raw = raw.get("manifest")
    spec_raw = raw.get("spec")
    if not isinstance(manifest_raw, Mapping) or not isinstance(spec_raw, Mapping):
        raise RegistryError("registry entry requires manifest and spec objects")

    artifact_raw = manifest_raw.get("artifact")
    resource_raw = spec_raw.get("resource")
    if not isinstance(artifact_raw, Mapping) or not isinstance(resource_raw, Mapping):
        raise RegistryError("manifest artifact and spec resource are required objects")

    try:
        resource = ResourceContract(
            ram_soft_mb=int(resource_raw["ram_soft_mb"]),
            ram_hard_mb=int(resource_raw["ram_hard_mb"]),
            disk_mb=int(resource_raw.get("disk_mb", 0)),
            cpu_threads=int(resource_raw.get("cpu_threads", 1)),
            max_concurrency=int(resource_raw.get("max_concurrency", 1)),
        )
        artifact = ArtifactSpec(
            repository_url=str(artifact_raw["repository_url"]),
            pinned_commit=str(artifact_raw["pinned_commit"]),
            sha256=(
                str(artifact_raw["sha256"])
                if artifact_raw.get("sha256") is not None
                else None
            ),
            subdirectory=str(artifact_raw.get("subdirectory", "")),
        )
        manifest = CapabilityManifest(
            capability_id=str(manifest_raw["capability_id"]),
            version=str(manifest_raw["version"]),
            artifact=artifact,
            description=str(manifest_raw.get("description", "")),
        )
        permissions_raw = spec_raw.get("permissions", [])
        if not isinstance(permissions_raw, list) or not all(
            isinstance(value, str) for value in permissions_raw
        ):
            raise RegistryError("spec permissions must be an array of strings")
        spec = CapabilitySpec(
            capability_id=str(spec_raw["capability_id"]),
            version=str(spec_raw["version"]),
            description=str(spec_raw["description"]),
            resource=resource,
            permissions=frozenset(permissions_raw),
            verification_required=bool(spec_raw.get("verification_required", True)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RegistryError("invalid registry entry fields") from exc

    return RegistryEntry(manifest=manifest, spec=spec)
