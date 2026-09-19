import unittest

from benchmarks.benchmark_security_posture import benchmark


class SecurityBenchmarkTests(unittest.TestCase):
    def test_benchmark(self):
        result=benchmark(3)
        self.assertEqual(result["iterations"],3)
        self.assertEqual(result["fingerprint_length"],64)
        self.assertEqual(result["controls"],10)
