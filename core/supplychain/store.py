from __future__ import annotations

from dataclasses import dataclass

from .models import ArtifactRecord
from .policy import ArtifactAdmissionPolicy, TrustDecision


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    key: str
    record: ArtifactRecord
    decision: TrustDecision


class ArtifactStore:
    """In-memory reference store; persistence remains an application boundary."""

    def __init__(self, policy: ArtifactAdmissionPolicy | None = None) -> None:
        self._policy = policy or ArtifactAdmissionPolicy()
        self._items: dict[str, StoredArtifact] = {}

    def admit(self, record: ArtifactRecord) -> StoredArtifact:
        decision = self._policy.evaluate(record)
        if not decision.accepted:
            raise ValueError("artifact admission denied: " + "; ".join(decision.reasons))
        key = record.identity.repository_url + "@" + record.identity.commit
        stored = StoredArtifact(key, record, decision)
        self._items[key] = stored
        return stored

    def get(self, key: str) -> StoredArtifact | None:
        return self._items.get(key)

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))
