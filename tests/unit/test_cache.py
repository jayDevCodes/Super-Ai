from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.cache import ArtifactCache, CacheError


class ArtifactCacheTests(unittest.TestCase):
    def test_put_get_and_integrity(self):
        with TemporaryDirectory() as temp:
            cache = ArtifactCache(Path(temp), max_bytes=1024)
            entry = cache.put(b"hello")
            self.assertEqual(cache.get(entry.key), b"hello")
            self.assertEqual(cache.total_bytes(), 5)

    def test_corruption_is_detected(self):
        with TemporaryDirectory() as temp:
            cache = ArtifactCache(Path(temp), max_bytes=1024)
            entry = cache.put(b"hello")
            entry.path.write_bytes(b"tampered")
            with self.assertRaises(CacheError):
                cache.get(entry.key)

    def test_lru_eviction_is_bounded(self):
        with TemporaryDirectory() as temp:
            cache = ArtifactCache(Path(temp), max_bytes=8)
            first = cache.put(b"aaaa")
            second = cache.put(b"bbbb")
            cache.get(first.key)
            third = cache.put(b"cccc")
            self.assertIsNotNone(cache.get(first.key))
            self.assertIsNone(cache.get(second.key))
            self.assertIsNotNone(cache.get(third.key))
            self.assertLessEqual(cache.total_bytes(), 8)

    def test_invalid_key_is_rejected(self):
        with TemporaryDirectory() as temp:
            cache = ArtifactCache(Path(temp))
            with self.assertRaises(CacheError):
                cache.get("not-a-digest")


if __name__ == "__main__":
    unittest.main()
