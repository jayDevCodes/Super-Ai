from __future__ import annotations

import unittest

from benchmarks.benchmark_image_identity import benchmark


class ImageIdentityBenchmarkTests(unittest.TestCase):
    def test_benchmark_shape_is_stable(self):
        results = benchmark(iterations=100, warmup=10)
        self.assertEqual([item.operation for item in results], ["image_identity_validation", "image_identity_resolution"])
        for item in results:
            self.assertEqual(item.iterations, 100)
            self.assertEqual(item.warmup, 10)
            self.assertGreaterEqual(item.median_ns, 0)
            self.assertGreaterEqual(item.p95_ns, item.median_ns)
            self.assertGreaterEqual(item.max_ns, item.min_ns)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            benchmark(iterations=0)
        with self.assertRaises(ValueError):
            benchmark(warmup=-1)


if __name__ == "__main__":
    unittest.main()
