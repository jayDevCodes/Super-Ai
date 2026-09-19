import hashlib
import unittest

from core.supplychain import ArtifactIdentity, ArtifactRecord
from core.supplychain.canonical import fingerprint
from core.supplychain.verification import CallbackSignatureVerifier, DigestVerifier


class SupplyChainVerificationTests(unittest.TestCase):
    def test_digest_verification(self):
        payload = b"hello"
        record = ArtifactRecord(
            ArtifactIdentity(
                "https://github.com/example/tool",
                "a" * 40,
                hashlib.sha256(payload).hexdigest(),
            )
        )
        result = DigestVerifier().verify_bytes(record, payload)
        self.assertTrue(result.verified)
        self.assertEqual(len(fingerprint(record)), 64)

    def test_callback_signature_verifier(self):
        record = ArtifactRecord(
            ArtifactIdentity("https://github.com/example/tool", "a" * 40, "b" * 64)
        )
        # signature is required by the verifier contract; absent means false
        self.assertFalse(CallbackSignatureVerifier(lambda _: True).verify(record))
