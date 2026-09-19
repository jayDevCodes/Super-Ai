from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .models import ArtifactRecord


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    version: int
    records: tuple[ArtifactRecord, ...]

    def validate(self) -> None:
        if self.version <= 0:
            raise ValueError("registry snapshot version must be positive")
        seen: set[str] = set()
        for record in self.records:
            record.validate()
            key = record.identity.repository_url + "@" + record.identity.commit
            if key in seen:
                raise ValueError(f"duplicate registry identity: {key}")
            seen.add(key)

    @property
    def fingerprint(self) -> str:
        self.validate()
        material = []
        for record in sorted(
            self.records,
            key=lambda r: (r.identity.repository_url, r.identity.commit),
        ):
            material.append(
                {
                    "repo": record.identity.repository_url,
                    "commit": record.identity.commit,
                    "digest": record.identity.digest,
                }
            )
        payload = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RegistryDelta:
    added: tuple[ArtifactRecord, ...]
    removed: tuple[str, ...]
    changed: tuple[ArtifactRecord, ...]


class RegistrySyncEngine:
    """Pure deterministic reconciliation of locally trusted registry records."""

    @staticmethod
    def diff(current: RegistrySnapshot, incoming: RegistrySnapshot) -> RegistryDelta:
        current.validate()
        incoming.validate()
        a = {
            r.identity.repository_url + "@" + r.identity.commit: r
            for r in current.records
        }
        b = {
            r.identity.repository_url + "@" + r.identity.commit: r
            for r in incoming.records
        }
        added = tuple(b[key] for key in sorted(b.keys() - a.keys()))
        removed = tuple(sorted(a.keys() - b.keys()))
        changed = tuple(
            b[key]
            for key in sorted(a.keys() & b.keys())
            if b[key].identity.digest != a[key].identity.digest
            or b[key] != a[key]
        )
        return RegistryDelta(added=added, removed=removed, changed=changed)

    @staticmethod
    def apply(current: RegistrySnapshot, delta: RegistryDelta) -> RegistrySnapshot:
        current.validate()
        records = {
            r.identity.repository_url + "@" + r.identity.commit: r
            for r in current.records
        }
        for key in delta.removed:
            records.pop(key, None)
        for record in (*delta.added, *delta.changed):
            record.validate()
            records[record.identity.repository_url + "@" + record.identity.commit] = record
        result = RegistrySnapshot(
            version=current.version + 1,
            records=tuple(records[key] for key in sorted(records)),
        )
        result.validate()
        return result
