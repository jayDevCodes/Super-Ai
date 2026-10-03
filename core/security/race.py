from __future__ import annotations

from dataclasses import dataclass
import secrets
import threading


class FenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FenceToken:
    resource_id: str
    owner_id: str
    nonce: str

    def validate(self) -> None:
        for field in ("resource_id", "owner_id", "nonce"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or value.strip() != value:
                raise FenceError(f"{field} must be a non-empty trimmed string")


class OwnershipFence:
    """Small in-process guard against stale cleanup or replacement races."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._claims: dict[str, FenceToken] = {}

    def acquire(self, resource_id: str, owner_id: str) -> FenceToken:
        if (
            not isinstance(resource_id, str)
            or not isinstance(owner_id, str)
            or not resource_id
            or not owner_id
            or resource_id.strip() != resource_id
            or owner_id.strip() != owner_id
        ):
            raise FenceError("resource_id and owner_id are required")
        with self._lock:
            if resource_id in self._claims:
                raise FenceError("resource is already fenced")
            token = FenceToken(resource_id, owner_id, secrets.token_hex(16))
            self._claims[resource_id] = token
            return token

    def assert_owner(self, token: FenceToken) -> None:
        token.validate()
        with self._lock:
            current = self._claims.get(token.resource_id)
            if current != token:
                raise FenceError("fence token is stale or ownership changed")

    def release(self, token: FenceToken) -> None:
        token.validate()
        with self._lock:
            current = self._claims.get(token.resource_id)
            if current != token:
                raise FenceError("fence token is stale or ownership changed")
            self._claims.pop(token.resource_id, None)

    def replace(self, token: FenceToken, new_owner_id: str) -> FenceToken:
        """Atomically hand a resource to a new owner after an exact check."""
        token.validate()
        if (
            not isinstance(new_owner_id, str)
            or not new_owner_id
            or new_owner_id.strip() != new_owner_id
        ):
            raise FenceError("new_owner_id must be a non-empty trimmed string")
        with self._lock:
            current = self._claims.get(token.resource_id)
            if current != token:
                raise FenceError("fence token is stale or ownership changed")
            replacement = FenceToken(
                token.resource_id,
                new_owner_id,
                secrets.token_hex(16),
            )
            self._claims[token.resource_id] = replacement
            return replacement

    def is_claimed(self, resource_id: str) -> bool:
        with self._lock:
            return resource_id in self._claims
