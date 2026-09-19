from __future__ import annotations

from core.security.evidence import build_security_evidence
from core.security.posture import SecurityProfile


def benchmark(iterations: int = 1000) -> dict[str, float | int]:
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    profile = SecurityProfile()
    evidence=None
    for _ in range(iterations):
        evidence=build_security_evidence(profile)
    return {
        "iterations":iterations,
        "fingerprint_length":len(evidence.fingerprint),
        "controls":len(evidence.controls),
    }


if __name__ == "__main__":
    print(benchmark())
