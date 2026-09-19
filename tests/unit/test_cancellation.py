import unittest

from core.runtime.cancellation import CancellationToken


class CancellationTokenTests(unittest.TestCase):
    def test_starts_uncancelled(self):
        token = CancellationToken()
        self.assertFalse(token.is_cancelled())
        self.assertIsNone(token.reason)

    def test_first_cancel_wins_and_reason_is_bounded(self):
        token = CancellationToken()
        self.assertTrue(token.cancel("first reason"))
        self.assertFalse(token.cancel("second reason"))
        self.assertTrue(token.is_cancelled())
        self.assertEqual(token.reason, "first reason")

    def test_empty_reason_uses_default(self):
        token = CancellationToken()
        token.cancel("   ")
        self.assertEqual(token.reason, "cancelled by caller")


if __name__ == "__main__":
    unittest.main()
