from __future__ import annotations

from core.supplychain.locks import dependency_lock_fingerprint
from core.supplychain.mirror import MirrorEndpoint, MirrorSelector
from core.supplychain.models import ArtifactIdentity, ArtifactRecord, DependencyLock, SbomSummary, SignatureEnvelope, ProvenanceRecord
from core.supplychain.policy import ArtifactAdmissionPolicy
from core.supplychain.sync import RegistrySnapshot, RegistrySyncEngine


def benchmark(iterations: int = 1000) -> dict[str, object]:
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    commit="a"*40
    digest="b"*64
    record=ArtifactRecord(
        ArtifactIdentity("https://github.com/example/tool",commit,digest),
        SignatureEnvelope("key","ed25519","sig"),
        ProvenanceRecord("builder",commit,"container"),
        SbomSummary(1,("a",),0,0),
        DependencyLock((("a",digest),)),
    )
    policy=ArtifactAdmissionPolicy()
    current=RegistrySnapshot(1,())
    incoming=RegistrySnapshot(1,(record,))
    for _ in range(iterations):
        policy.evaluate(record)
        RegistrySyncEngine.diff(current,incoming)
        dependency_lock_fingerprint(record.dependency_lock)
        MirrorSelector((MirrorEndpoint("primary","https://mirror.example",10),)).choose()
    return {"iterations":iterations,"trust_score":policy.evaluate(record).score,"lock_bits":256}


if __name__=="__main__":
    print(benchmark())
