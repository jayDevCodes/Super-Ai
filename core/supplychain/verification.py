from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from .models import ArtifactRecord


class SignatureVerifier(Protocol):
    def verify(self, record: ArtifactRecord) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verified: bool
    reason: str


class DigestVerifier:
    """Verifies a byte payload against the artifact's immutable SHA-256 identity."""

    def verify_bytes(self, record: ArtifactRecord, payload: bytes) -> VerificationResult:
        try:
            record.validate()
        except ValueError as exc:
            return VerificationResult(False, str(exc))
        actual = hashlib.sha256(payload).hexdigest()
        if actual != record.identity.digest.lower():
            return VerificationResult(False, "payload digest does not match artifact identity")
        return VerificationResult(True, "payload digest matches artifact identity")


class CallbackSignatureVerifier:
    """Adapter for a real signature library without coupling the core to one crypto stack."""

    def __init__(self, callback):
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callback = callback

    def verify(self, record: ArtifactRecord) -> bool:
        record.validate()
        if record.signature is None:
            return False
        return bool(self._callback(record))
