from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .posture import SecurityProfile, SecurityAuditReport, SecurityAuditor
from .translation import compile_security_envelope


HARDENING_CONTROL_IDS: tuple[str, ...] = (
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


@dataclass(frozen=True, slots=True)
class HardeningEvidence:
    accepted: bool
    profile_fingerprint: str
    findings: tuple[str, ...]
    control_count: int
    control_ids: tuple[str, ...] = HARDENING_CONTROL_IDS


class HardeningController:
    def review(self, profile: SecurityProfile) -> HardeningEvidence:
        report: SecurityAuditReport = SecurityAuditor().review(profile)
        envelope = compile_security_envelope(profile) if report.accepted else None
        material = {
            "accepted": report.accepted,
            "findings": report.findings,
            "envelope": None if envelope is None else envelope.__dict__ if hasattr(envelope, "__dict__") else {
                "run_as_non_root": envelope.run_as_non_root,
                "no_new_privileges": envelope.no_new_privileges,
                "readonly_rootfs": envelope.readonly_rootfs,
                "syscall_mode": envelope.syscall_mode,
                "network_mode": envelope.network_mode,
                "allowed_hosts": list(envelope.allowed_hosts),
                "allowed_cidrs": list(envelope.allowed_cidrs),
                "allowed_writes": list(envelope.allowed_writes),
                "max_processes": envelope.max_processes,
                "max_open_files": envelope.max_open_files,
                "capabilities": list(envelope.capabilities),
            },
        }
        digest = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return HardeningEvidence(
            accepted=report.accepted,
            profile_fingerprint=digest,
            findings=report.findings,
            control_count=len(HARDENING_CONTROL_IDS),
            control_ids=HARDENING_CONTROL_IDS,
        )
