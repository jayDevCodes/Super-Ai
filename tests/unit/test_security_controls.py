import unittest

from core.security.hardening import HardeningController
from core.security.posture import SecurityProfile
from core.security.quotas import QuotaError, QuotaLedger, ResourceQuota
from core.security.translation import security_arguments


class SecurityControlsTests(unittest.TestCase):
    def test_security_translation(self):
        profile = SecurityProfile()
        evidence = HardeningController().review(profile)
        self.assertTrue(evidence.accepted)
        self.assertIn("--non-root", security_arguments(profile))
        self.assertIn("--network=disabled", security_arguments(profile))

    def test_quota_ledger(self):
        ledger = QuotaLedger(ResourceQuota(1000, 2, 2000, 20))
        request = ResourceQuota(400, 1, 500, 5)
        ledger.reserve(request)
        self.assertEqual(ledger.available.memory_mb, 600)
        ledger.release(request)
        self.assertEqual(ledger.available.memory_mb, 1000)

    def test_quota_overflow(self):
        ledger = QuotaLedger(ResourceQuota(1000, 1, 1000, 1))
        with self.assertRaises(QuotaError):
            ledger.reserve(ResourceQuota(1001, 1, 1, 1))

    def test_lease_is_single_use_and_exact(self):
        ledger = QuotaLedger(ResourceQuota(1000, 2, 2000, 20))
        reservation = ledger.reserve_lease(ResourceQuota(400, 1, 500, 5))
        self.assertEqual(ledger.used.memory_mb, 400)
        ledger.release_lease(reservation)
        self.assertEqual(ledger.available.memory_mb, 1000)
        with self.assertRaises(QuotaError):
            ledger.release_lease(reservation)

    def test_mismatched_lease_cannot_release_reservation(self):
        ledger = QuotaLedger(ResourceQuota(1000, 2, 2000, 20))
        reservation = ledger.reserve_lease(ResourceQuota(400, 1, 500, 5))
        wrong = type(reservation)(reservation.reservation_id, ResourceQuota(300, 1, 500, 5))
        with self.assertRaises(QuotaError):
            ledger.release_lease(wrong)
        self.assertEqual(ledger.used.memory_mb, 400)
        ledger.release_lease(reservation)
