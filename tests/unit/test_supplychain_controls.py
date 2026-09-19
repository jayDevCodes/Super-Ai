import unittest

from core.supplychain.locks import dependency_lock_fingerprint, lock_matches
from core.supplychain.mirror import MirrorEndpoint, MirrorSelector
from core.supplychain.models import DependencyLock, RevocationEntry
from core.supplychain.revocation import RevocationIndex


class SupplyChainControlTests(unittest.TestCase):
    def test_mirror_order_is_deterministic(self):
        mirrors = MirrorSelector((
            MirrorEndpoint("b", "https://b.example", 20),
            MirrorEndpoint("a", "https://a.example", 10),
        ))
        self.assertEqual([m.name for m in mirrors.ordered()], ["a", "b"])

    def test_revocation_expiry(self):
        entry = RevocationEntry("subject", "bad", expires_at_epoch=100)
        index = RevocationIndex((entry,))
        self.assertTrue(index.is_revoked("subject", now_epoch=99))
        self.assertFalse(index.is_revoked("subject", now_epoch=100))

    def test_lock_fingerprint_and_match(self):
        lock = DependencyLock((("z", "b" * 64), ("a", "a" * 64)))
        self.assertEqual(len(dependency_lock_fingerprint(lock)), 64)
        self.assertTrue(lock_matches(lock, {"a": "A" * 64, "z": "B" * 64}))
