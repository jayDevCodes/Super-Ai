from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

from typing import Protocol


class _Runner(Protocol):
    def run(self, command, *, cwd, environment, timeout_seconds): ...


class PreflightError(RuntimeError):
    """Raised when the Apple Container runtime cannot be trusted for execution."""


@dataclass(frozen=True, slots=True)
class ImageIdentity:
    """Resolved local image identity from Apple Container inspect output."""

    reference: str
    digest: str

    def validate(self) -> None:
        if not self.reference:
            raise ValueError("image reference must be non-empty")
        if not _DIGEST_RE.fullmatch(self.digest):
            raise ValueError("image digest must be sha256:<64 hex>")


class AppleContainerPreflight:
    """Check container service health and resolve immutable image identity."""

    def __init__(self, runner, *, cwd, environment: Mapping[str, str], timeout_seconds: float = 10.0):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner: _Runner = runner
        self._cwd = cwd
        self._environment = dict(environment)
        self._timeout_seconds = timeout_seconds

    def require_healthy_system(self) -> Mapping[str, Any]:
        result: CommandResult = self._runner.run(
            ("container", "system", "status", "--format", "json"),
            cwd=self._cwd,
            environment=self._environment,
            timeout_seconds=self._timeout_seconds,
        )
        if result.returncode != 0:
            raise PreflightError(
                "Apple Container system status is unhealthy"
            )
        payload = _decode_json(result.stdout, "system status")
        if isinstance(payload, dict):
            status = str(payload.get("status", "")).lower()
            if status and status not in {"running", "ready", "healthy", "ok"}:
                raise PreflightError(
                    f"Apple Container system reports status {status!r}"
                )
        return payload if isinstance(payload, dict) else {"raw": payload}

    def resolve_image(self, image_reference: str) -> ImageIdentity:
        if not image_reference or image_reference.strip() != image_reference:
            raise PreflightError("image reference must be non-empty and trimmed")

        result: CommandResult = self._runner.run(
            ("container", "image", "inspect", image_reference),
            cwd=self._cwd,
            environment=self._environment,
            timeout_seconds=self._timeout_seconds,
        )
        if result.returncode != 0:
            raise PreflightError(
                f"container image inspect failed for {image_reference!r}"
            )

        payload = _decode_json(result.stdout, "image inspect")
        if not isinstance(payload, list) or len(payload) != 1:
            raise PreflightError(
                "image inspect must return exactly one image"
            )

        item = payload[0]
        if not isinstance(item, dict):
            raise PreflightError("image inspect entry must be an object")

        configuration = item.get("configuration")
        if not isinstance(configuration, dict):
            raise PreflightError("image inspect is missing configuration")

        name = configuration.get("name")
        if not isinstance(name, str):
            raise PreflightError("image inspect is missing image name")

        descriptor = configuration.get("descriptor")
        if not isinstance(descriptor, dict):
            raise PreflightError("image inspect is missing image descriptor")

        digest = descriptor.get("digest")
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise PreflightError("image inspect is missing a valid sha256 digest")

        identity = ImageIdentity(reference=name, digest=digest)
        identity.validate()
        return identity


def _decode_json(payload: bytes, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"{label} output is not valid JSON") from exc


_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
