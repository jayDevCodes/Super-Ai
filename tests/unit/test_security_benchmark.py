import unittest

from benchmarks.benchmark_security_posture import benchmark
from core.security import HARDENING_CONTROL_IDS, HardeningController
from core.security.posture import SecurityProfile


class SecurityBenchmarkTests(unittest.TestCase):
    def test_benchmark(self):
        result=benchmark(3)
        self.assertEqual(result["iterations"],3)
        self.assertEqual(result["fingerprint_length"],64)
        self.assertEqual(result["controls"],10)

    def test_hardening_evidence_names_every_control(self):
        evidence = HardeningController().review(SecurityProfile())
        self.assertEqual(evidence.control_ids, HARDENING_CONTROL_IDS)
        self.assertEqual(evidence.control_count, len(HARDENING_CONTROL_IDS))
