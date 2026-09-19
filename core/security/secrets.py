from __future__ import annotations

from dataclasses import dataclass

from core.security.environment import is_sensitive_name


@dataclass(frozen=True, slots=True)
class SecretScan:
    safe: bool
    sensitive_names: tuple[str, ...]


class SecretBoundaryScanner:
    def scan(self, environment: dict[str, str]) -> SecretScan:
        sensitive = tuple(sorted(name for name in environment if is_sensitive_name(name)))
        return SecretScan(not sensitive, sensitive)

    def sanitize(self, environment: dict[str, str]) -> dict[str, str]:
        scan = self.scan(environment)
        if not scan.safe:
            raise ValueError("sensitive environment variables detected: " + ", ".join(scan.sensitive_names))
        return dict(environment)
