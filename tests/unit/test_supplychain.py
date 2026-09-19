import unittest

from core.supplychain import (
    ArtifactAdmissionPolicy,
    ArtifactIdentity,
    ArtifactRecord,
    DependencyLock,
    ProvenanceRecord,
    RegistrySnapshot,
    RegistrySyncEngine,
    SbomSummary,
    SignatureEnvelope,
)


COMMIT = "a" * 40
DIGEST = "b" * 64


def record() -> ArtifactRecord:
    return ArtifactRecord(
        identity=ArtifactIdentity("https://github.com/example/tool", COMMIT, DIGEST),
        signature=SignatureEnvelope("key-1", "ed25519", "sig"),
        provenance=ProvenanceRecord("builder-1", COMMIT, "container", ("source",)),
        sbom=SbomSummary(4, ("a", "b"), 0, 0),
        dependency_lock=DependencyLock((("a", DIGEST),)),
    )


class SupplyChainTests(unittest.TestCase):
    def test_admitted_evidence(self):
        decision = ArtifactAdmissionPolicy().evaluate(record())
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.score, 100)

    def test_missing_evidence_rejected(self):
        minimal = ArtifactRecord(ArtifactIdentity(
            "https://github.com/example/tool", COMMIT, DIGEST
        ))
        decision = ArtifactAdmissionPolicy().evaluate(minimal)
        self.assertFalse(decision.accepted)

    def test_registry_diff_apply(self):
        current = RegistrySnapshot(1, ())
        incoming = RegistrySnapshot(1, (record(),))
        delta = RegistrySyncEngine.diff(current, incoming)
        result = RegistrySyncEngine.apply(current, delta)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.fingerprint, incoming.fingerprint)
