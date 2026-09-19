from __future__ import annotations

from dataclasses import dataclass
import json
import re
import uuid
from typing import Any, Mapping


class OwnershipError(RuntimeError):
    """Raised when a container cannot be proven to belong to this execution."""


@dataclass(frozen=True, slots=True)
class OwnershipClaim:
    """Unique execution ownership metadata attached to a container."""

    execution_id: str
    container_id: str
    owner: str = "super-ai"
    owner_label: str = "com.super-ai.owner"
    execution_label: str = "com.super-ai.execution"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", self.execution_id):
            raise ValueError("execution_id must be a 32-character lowercase hex UUID")
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$", self.container_id):
            raise ValueError("container_id contains unsupported characters")
        if not self.owner:
            raise ValueError("owner must be non-empty")

    @property
    def labels(self) -> Mapping[str, str]:
        return {
            self.owner_label: self.owner,
            self.execution_label: self.execution_id,
        }


def new_ownership_claim() -> OwnershipClaim:
    execution_id = uuid.uuid4().hex
    return OwnershipClaim(
        execution_id=execution_id,
        container_id=f"super-ai-{execution_id[:24]}",
    )


def verify_container_ownership(
    payload: bytes | str | Mapping[str, Any],
    claim: OwnershipClaim,
) -> None:
    """Fail closed unless inspect output proves the exact execution owns it."""
    document = _decode_document(payload)
    if not isinstance(document, list) or len(document) != 1:
        raise OwnershipError("container inspect must return exactly one container")
    item = document[0]
    if not isinstance(item, dict):
        raise OwnershipError("container inspect entry must be an object")

    configuration = item.get("configuration")
    if not isinstance(configuration, dict):
        raise OwnershipError("inspect result is missing configuration")

    observed_id = configuration.get("id")
    if observed_id != claim.container_id:
        raise OwnershipError("container ID does not match ownership claim")

    labels = configuration.get("labels")
    if not isinstance(labels, dict):
        raise OwnershipError("container inspect is missing ownership labels")

    for key, expected in claim.labels.items():
        observed = labels.get(key)
        if observed != expected:
            raise OwnershipError(
                f"ownership label mismatch for {key!r}"
            )


def _decode_document(payload: bytes | str | Mapping[str, Any] | list[Any]) -> Any:
    if isinstance(payload, (dict, list)):
        return payload
    try:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnershipError("container inspect output is not valid JSON") from exc
