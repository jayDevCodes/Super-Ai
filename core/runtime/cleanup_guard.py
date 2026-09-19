from __future__ import annotations

from dataclasses import dataclass

from core.security.race import FenceToken, OwnershipFence


@dataclass(frozen=True, slots=True)
class CleanupClaim:
    resource_id: str
    owner_id: str
    token: FenceToken


class CleanupGuard:
    """Runtime adapter that refuses stale cleanup claims."""

    def __init__(self, fence: OwnershipFence | None = None) -> None:
        self._fence = fence or OwnershipFence()

    def claim(self, resource_id: str, owner_id: str) -> CleanupClaim:
        token = self._fence.acquire(resource_id, owner_id)
        return CleanupClaim(resource_id, owner_id, token)

    def assert_current(self, claim: CleanupClaim) -> None:
        self._fence.assert_owner(claim.token)

    def release(self, claim: CleanupClaim) -> None:
        self._fence.assert_owner(claim.token)
        self._fence.release(claim.token)
