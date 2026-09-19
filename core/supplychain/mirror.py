from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


class MirrorPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MirrorEndpoint:
    name: str
    base_url: str
    priority: int = 100
    read_only: bool = True

    def validate(self) -> None:
        if not self.name or self.name.strip() != self.name:
            raise MirrorPolicyError("mirror name must be trimmed")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise MirrorPolicyError("mirror base_url must be a clean HTTPS URL")
        if self.priority < 0:
            raise MirrorPolicyError("mirror priority cannot be negative")


class MirrorSelector:
    def __init__(self, endpoints: tuple[MirrorEndpoint, ...] = ()) -> None:
        for endpoint in endpoints:
            endpoint.validate()
        self._endpoints = tuple(sorted(endpoints, key=lambda e: (e.priority, e.name)))

    def ordered(self) -> tuple[MirrorEndpoint, ...]:
        return self._endpoints

    def choose(self, unavailable: set[str] | None = None) -> MirrorEndpoint | None:
        blocked = unavailable or set()
        return next((e for e in self._endpoints if e.name not in blocked), None)
