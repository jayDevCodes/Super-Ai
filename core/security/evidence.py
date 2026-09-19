from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .posture import SecurityProfile
from .translation import compile_security_envelope


@dataclass(frozen=True, slots=True)
class SecurityEvidence:
    fingerprint: str
    controls: tuple[str, ...]
    network: str
    write_roots: tuple[str, ...]


def build_security_evidence(profile: SecurityProfile) -> SecurityEvidence:
    profile.validate()
    envelope=compile_security_envelope(profile)
    controls=(
        "non-root",
        "no-new-privileges",
        "syscall-posture",
        "filesystem-isolation",
        "network-policy",
        "secret-boundary",
        "process-quota",
        "open-file-quota",
        "capability-boundary",
        "ownership-race-fence",
    )
    material={
        "controls":controls,
        "network":envelope.network_mode,
        "write_roots":envelope.allowed_writes,
        "capabilities":envelope.capabilities,
        "processes":envelope.max_processes,
        "files":envelope.max_open_files,
    }
    digest=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return SecurityEvidence(digest,controls,envelope.network_mode,envelope.allowed_writes)
