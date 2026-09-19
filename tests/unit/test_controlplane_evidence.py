import unittest

from core.controlplane.evidence import make_evidence


class ControlEvidenceTests(unittest.TestCase):
    def test_evidence_is_stable(self):
        first=make_evidence("runtime","accepted",{"b":2,"a":1})
        second=make_evidence("runtime","accepted",{"a":1,"b":2})
        self.assertEqual(first.fingerprint,second.fingerprint)
        self.assertEqual(len(first.fingerprint),64)
