from __future__ import annotations


class CapabilityBoundaryError(ValueError):
    pass


class CapabilityBoundary:
    def __init__(self, allowlist: frozenset[str] = frozenset()) -> None:
        forbidden = {"ALL", "CAP_SYS_ADMIN", "CAP_SYS_PTRACE", "CAP_NET_ADMIN"}
        if forbidden.intersection(allowlist):
            raise CapabilityBoundaryError("administrative or wildcard capabilities are forbidden")
        if any(not item or item.strip() != item for item in allowlist):
            raise CapabilityBoundaryError("capability names must be trimmed and non-empty")
        self._allowlist = frozenset(allowlist)

    def validate_request(self, requested: frozenset[str]) -> None:
        if not requested <= self._allowlist:
            missing = sorted(requested - self._allowlist)
            raise CapabilityBoundaryError("capabilities not allowlisted: " + ", ".join(missing))

    def allowed(self) -> frozenset[str]:
        return self._allowlist
