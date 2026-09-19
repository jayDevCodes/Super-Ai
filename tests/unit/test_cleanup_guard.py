import unittest

from core.runtime.cleanup_guard import CleanupGuard
from core.security.race import FenceError


class CleanupGuardTests(unittest.TestCase):
    def test_claim_lifecycle(self):
        guard=CleanupGuard()
        claim=guard.claim("c1","owner1")
        guard.assert_current(claim)
        guard.release(claim)

    def test_duplicate_claim_fails(self):
        guard=CleanupGuard()
        claim=guard.claim("c1","owner1")
        try:
            with self.assertRaises(FenceError):
                guard.claim("c1","owner2")
        finally:
            guard.release(claim)
