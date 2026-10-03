import unittest
from concurrent.futures import ThreadPoolExecutor

from core.security.posture import NetworkEgress, NetworkMode, SecurityAuditor, SecurityProfile
from core.security.race import FenceError, OwnershipFence


class SecurityPostureTests(unittest.TestCase):
    def test_default_profile_is_accepted(self):
        report = SecurityAuditor().review(SecurityProfile())
        self.assertTrue(report.accepted)

    def test_network_default_denies(self):
        network = NetworkEgress()
        self.assertFalse(network.permits_ip("1.1.1.1"))

    def test_allowlisted_network(self):
        network = NetworkEgress(
            NetworkMode.ALLOWLIST,
            allowed_cidrs=("10.0.0.0/8",),
        )
        self.assertTrue(network.permits_ip("10.2.3.4"))
        self.assertFalse(network.permits_ip("8.8.8.8"))

    def test_fence_rejects_stale_cleanup(self):
        fence = OwnershipFence()
        token = fence.acquire("container-1", "owner-a")
        with self.assertRaises(FenceError):
            fence.acquire("container-1", "owner-b")
        fence.assert_owner(token)
        fence.release(token)
        self.assertFalse(fence.is_claimed("container-1"))

    def test_fence_replacement_is_atomic_and_invalidates_old_token(self):
        fence = OwnershipFence()
        token = fence.acquire("container-1", "owner-a")
        replacement = fence.replace(token, "owner-b")
        with self.assertRaises(FenceError):
            fence.assert_owner(token)
        fence.assert_owner(replacement)
        fence.release(replacement)

    def test_concurrent_acquire_has_one_winner(self):
        fence = OwnershipFence()

        def claim(index: int):
            try:
                return fence.acquire("container-race", f"owner-{index}")
            except FenceError:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = tuple(pool.map(claim, range(8)))
        winners = tuple(result for result in results if result is not None)
        self.assertEqual(len(winners), 1)
        fence.release(winners[0])

    def test_fence_rejects_untrimmed_identifiers(self):
        fence = OwnershipFence()
        with self.assertRaises(FenceError):
            fence.acquire(" container-1", "owner-a")
