from __future__ import annotations

import unittest

from benchmarks.benchmark_runtime_specs import benchmark


class RuntimeSpecBenchmarkTests(unittest.TestCase):
    def test_benchmark_shape_is_stable(self):
        summary = benchmark(iterations=100, warmup=10)
        self.assertEqual(summary.iterations, 100)
        self.assertEqual(summary.warmup, 10)
        self.assertGreaterEqual(summary.median_ns, 0)
        self.assertGreaterEqual(summary.p95_ns, summary.median_ns)
        self.assertGreaterEqual(summary.min_ns, 0)
        self.assertGreaterEqual(summary.max_ns, summary.min_ns)

    def test_invalid_benchmark_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            benchmark(iterations=0)
        with self.assertRaises(ValueError):
            benchmark(warmup=-1)


if __name__ == "__main__":
    unittest.main()
