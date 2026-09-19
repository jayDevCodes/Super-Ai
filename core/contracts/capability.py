from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .resources import ResourceContract


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Static metadata used by the router and scheduler."""

    capability_id: str
    version: str
    description: str
    resource: ResourceContract
    permissions: frozenset[str] = frozenset()
    verification_required: bool = True

    def validate(self) -> None:
        if not self.capability_id or self.capability_id.strip() != self.capability_id:
            raise ValueError("capability_id must be a non-empty trimmed string")
        if not self.version or self.version.strip() != self.version:
            raise ValueError("version must be a non-empty trimmed string")
        if not self.description.strip():
            raise ValueError("description must be non-empty")
        self.resource.validate()
        if any(not permission.strip() for permission in self.permissions):
            raise ValueError("permissions must contain only non-empty strings")


class Capability(Protocol):
    """Runtime contract every executable capability must satisfy."""

    spec: CapabilitySpec

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        ...

    def verify(self, input_data: dict[str, Any], output_data: dict[str, Any]) -> bool:
        ...

    def cleanup(self) -> None:
        ...
