from __future__ import annotations

import unittest

from core.security.secrets import (
    SecretBoundaryError,
    SecretBoundaryPolicy,
    SecretBoundaryScanner,
)


class SecretBoundaryTests(unittest.TestCase):
    def test_sensitive_names_are_rejected_without_exposing_values(self):
        value = "super-secret-token-value"
        scan = SecretBoundaryScanner().scan({"API_KEY": value, "MODE": "smoke"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.sensitive_names, ("API_KEY",))
        self.assertNotIn(value, str(scan))
        with self.assertRaises(SecretBoundaryError) as raised:
            SecretBoundaryScanner().sanitize({"API_KEY": value})
        self.assertNotIn(value, str(raised.exception))

    def test_invalid_environment_name_is_rejected(self):
        scan = SecretBoundaryScanner().scan({"BAD-NAME": "value"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.invalid_names, ("BAD-NAME",))

    def test_non_string_value_is_rejected(self):
        scan = SecretBoundaryScanner().scan({"MODE": 123})  # type: ignore[arg-type]
        self.assertFalse(scan.safe)
        self.assertEqual(scan.invalid_values, ("MODE",))

    def test_single_value_size_is_bounded(self):
        policy = SecretBoundaryPolicy(max_value_bytes=4, max_total_value_bytes=8)
        scan = SecretBoundaryScanner(policy).scan({"MODE": "12345"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.oversized_values, ("MODE",))

    def test_total_value_size_is_bounded(self):
        policy = SecretBoundaryPolicy(max_value_bytes=8, max_total_value_bytes=8)
        scan = SecretBoundaryScanner(policy).scan({"A": "1234", "B": "56789"})
        self.assertFalse(scan.safe)
        self.assertTrue(scan.total_value_limit_exceeded)

    def test_variable_count_is_bounded(self):
        policy = SecretBoundaryPolicy(max_variables=2)
        scan = SecretBoundaryScanner(policy).scan(
            {"A": "1", "B": "2", "C": "3"}
        )
        self.assertFalse(scan.safe)
        self.assertTrue(scan.too_many_variables)

    def test_control_characters_are_rejected(self):
        scan = SecretBoundaryScanner().scan({"MODE": "bad\nvalue"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.invalid_values, ("MODE",))

    def test_safe_environment_round_trips(self):
        environment = {"PATH": "/usr/bin", "LANG": "C", "MODE": "smoke"}
        scan = SecretBoundaryScanner().scan(environment)
        self.assertTrue(scan.safe)
        self.assertEqual(SecretBoundaryScanner().sanitize(environment), environment)

    def test_policy_is_validated(self):
        with self.assertRaises(ValueError):
            SecretBoundaryPolicy(max_value_bytes=0)
        with self.assertRaises(ValueError):
            SecretBoundaryPolicy(max_value_bytes=10, max_total_value_bytes=9)
        with self.assertRaises(ValueError):
            SecretBoundaryPolicy(forbidden_names=("BAD-NAME",))

    def test_explicit_forbidden_name_is_rejected(self):
        policy = SecretBoundaryPolicy(forbidden_names=("INTERNAL_SECRET",))
        scan = SecretBoundaryScanner(policy).scan({"INTERNAL_SECRET": "value"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.sensitive_names, ("INTERNAL_SECRET",))

    def test_evidence_contains_no_secret_values(self):
        value = "super-secret-token-value"
        evidence = SecretBoundaryScanner().evidence({"API_KEY": value})
        self.assertFalse(evidence.accepted)
        self.assertEqual(evidence.variable_count, 1)
        self.assertEqual(evidence.sensitive_name_count, 1)
        self.assertNotIn(value, str(evidence))

    def test_evidence_fingerprint_is_deterministic(self):
        environment = {"MODE": "smoke"}
        scanner = SecretBoundaryScanner()
        self.assertEqual(scanner.evidence(environment), scanner.evidence(environment))


if __name__ == "__main__":
    unittest.main()
