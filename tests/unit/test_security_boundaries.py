import unittest

from core.security.capabilities import CapabilityBoundary, CapabilityBoundaryError
from core.security.network import NetworkBoundary
from core.security.secrets import SecretBoundaryScanner


class SecurityBoundaryTests(unittest.TestCase):
    def test_capability_allowlist(self):
        boundary = CapabilityBoundary(frozenset({"CAP_CHOWN"}))
        boundary.validate_request(frozenset({"CAP_CHOWN"}))
        with self.assertRaises(CapabilityBoundaryError):
            boundary.validate_request(frozenset({"CAP_SYS_ADMIN"}))

    def test_https_host_allowlist(self):
        boundary = NetworkBoundary(frozenset({"example.com"}))
        self.assertTrue(boundary.permits_url("https://example.com/path"))
        self.assertFalse(boundary.permits_url("http://example.com/path"))

    def test_secret_scanner(self):
        scan = SecretBoundaryScanner().scan({"PATH": "/bin", "API_KEY": "x"})
        self.assertFalse(scan.safe)
        self.assertEqual(scan.sensitive_names, ("API_KEY",))
