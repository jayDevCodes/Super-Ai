from __future__ import annotations

import hashlib
import json

from .models import ArtifactRecord


def canonical_record(record: ArtifactRecord) -> bytes:
    record.validate()
    payload = {
        "identity": {
            "repository_url": record.identity.repository_url,
            "commit": record.identity.commit,
            "digest": record.identity.digest.lower(),
        },
        "signature": None if record.signature is None else {
            "key_id": record.signature.key_id,
            "algorithm": record.signature.algorithm,
            "value": record.signature.value,
        },
        "provenance": None if record.provenance is None else {
            "builder_id": record.provenance.builder_id,
            "source_commit": record.provenance.source_commit,
            "build_type": record.provenance.build_type,
            "materials": list(record.provenance.materials),
        },
        "sbom": None if record.sbom is None else {
            "package_count": record.sbom.package_count,
            "direct_dependencies": list(record.sbom.direct_dependencies),
            "known_vulnerabilities": record.sbom.known_vulnerabilities,
            "critical_vulnerabilities": record.sbom.critical_vulnerabilities,
        },
        "dependency_lock": None if record.dependency_lock is None else list(record.dependency_lock.entries),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fingerprint(record: ArtifactRecord) -> str:
    return hashlib.sha256(canonical_record(record)).hexdigest()
