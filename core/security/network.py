from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from urllib.parse import urlparse


class NetworkBoundaryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NetworkBoundary:
    allowed_hosts: frozenset[str] = frozenset()
    allowed_cidrs: tuple[str, ...] = ()

    def validate(self) -> None:
        for host in self.allowed_hosts:
            if not host or any(c in host for c in "\x00\r\n /:@"):
                raise NetworkBoundaryError("invalid allowlisted host")
        for cidr in self.allowed_cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise NetworkBoundaryError("invalid allowlisted CIDR") from exc

    def permits_url(self, url: str) -> bool:
        self.validate()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        return parsed.hostname.lower() in {h.lower() for h in self.allowed_hosts}

    def permits_ip(self, address: str) -> bool:
        self.validate()
        ip = ipaddress.ip_address(address)
        return any(ip in ipaddress.ip_network(c, strict=False) for c in self.allowed_cidrs)
