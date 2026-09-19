import unittest

from core.security.evidence import build_security_evidence
from core.security.posture import SecurityProfile


class SecurityEvidenceTests(unittest.TestCase):
    def test_evidence_is_deterministic(self):
        a=build_security_evidence(SecurityProfile())
        b=build_security_evidence(SecurityProfile())
        self.assertEqual(a.fingerprint,b.fingerprint)
        self.assertEqual(len(a.controls),10)
