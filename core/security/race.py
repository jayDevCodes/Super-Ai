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


class OwnershipFence:
    """Small in-process guard against stale cleanup or replacement races."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._claims: dict[str, FenceToken] = {}

    def acquire(self, resource_id: str, owner_id: str) -> FenceToken:
        if not resource_id or not owner_id:
            raise FenceError("resource_id and owner_id are required")
        with self._lock:
            if resource_id in self._claims:
                raise FenceError("resource is already fenced")
            token = FenceToken(resource_id, owner_id, secrets.token_hex(16))
            self._claims[resource_id] = token
            return token

    def assert_owner(self, token: FenceToken) -> None:
        with self._lock:
            current = self._claims.get(token.resource_id)
            if current != token:
                raise FenceError("fence token is stale or ownership changed")

    def release(self, token: FenceToken) -> None:
        self.assert_owner(token)
        with self._lock:
            self._claims.pop(token.resource_id, None)

    def is_claimed(self, resource_id: str) -> bool:
        with self._lock:
            return resource_id in self._claims
