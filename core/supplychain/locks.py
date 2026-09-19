from __future__ import annotations

import hashlib
import json

from .models import DependencyLock


def dependency_lock_fingerprint(lock: DependencyLock) -> str:
    lock.validate()
    material = [[name, digest.lower()] for name, digest in sorted(lock.entries)]
    return hashlib.sha256(
        json.dumps(material, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def lock_matches(lock: DependencyLock, expected: dict[str, str]) -> bool:
    lock.validate()
    normalized = {k: v.lower() for k, v in lock.as_dict().items()}
    target = {k: v.lower() for k, v in expected.items()}
    return normalized == target
