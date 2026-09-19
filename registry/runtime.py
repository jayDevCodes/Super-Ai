from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


class RuntimeSpecError(ValueError):
    """Raised when runtime execution metadata is invalid."""


_EXECUTABLE_TOKEN_RE = re.compile(r"^[^\x00\r\n]{1,256}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    """Immutable runtime execution identity for a capability."""

    image: str
    command: tuple[str, ...]
    timeout_seconds: float = 60.0
    expected_image_digest: str | None = None
    working_directory: str = "/workspace"

    def validate(self) -> None:
        if not self.image or self.image.strip() != self.image:
            raise RuntimeSpecError("image must be a non-empty trimmed string")
        parsed = urlparse(self.image)
        if parsed.scheme or parsed.query or parsed.fragment:
            raise RuntimeSpecError("image must be a container image reference, not a URL")

        if not self.command:
            raise RuntimeSpecError("command must contain at least one argv element")
        for index, token in enumerate(self.command):
            if not isinstance(token, str) or not _EXECUTABLE_TOKEN_RE.fullmatch(token):
                raise RuntimeSpecError(
                    f"command[{index}] must be a non-empty bounded token without NUL/newlines"
                )

        if self.timeout_seconds <= 0 or self.timeout_seconds > 3600:
            raise RuntimeSpecError("timeout_seconds must be > 0 and <= 3600")

        if self.expected_image_digest is not None and not _DIGEST_RE.fullmatch(
            self.expected_image_digest
        ):
            raise RuntimeSpecError(
                "expected_image_digest must use the sha256:<64-hex> format"
            )

        if not self.working_directory.startswith("/"):
            raise RuntimeSpecError("working_directory must be an absolute container path")
        if any(char in self.working_directory for char in "\x00\r\n"):
            raise RuntimeSpecError("working_directory contains unsafe control characters")
