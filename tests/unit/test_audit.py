from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from core.audit import AuditError, HashChainAuditStore


class AuditStoreTests(unittest.TestCase):
    def test_append_and_verify_hash_chain(self):
        with TemporaryDirectory() as temp:
            store = HashChainAuditStore(Path(temp) / "audit.jsonl")
            first = store.append("runtime.started", {"task_id": "T1"})
            second = store.append("runtime.finished", {"success": True})
            self.assertEqual(first.sequence, 1)
            self.assertEqual(second.sequence, 2)
            self.assertEqual(second.previous_hash, first.event_hash)
            self.assertTrue(store.verify())

    def test_tampering_is_detected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "audit.jsonl"
            store = HashChainAuditStore(path)
            store.append("test", {"value": 1})
            raw = json.loads(path.read_text())
            raw["attributes"]["value"] = 2
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
            with self.assertRaises(AuditError):
                store.verify()

    def test_log_injection_is_rejected(self):
        with TemporaryDirectory() as temp:
            store = HashChainAuditStore(Path(temp) / "audit.jsonl")
            with self.assertRaises(AuditError):
                store.append("test", {"message": "bad\\nline"})

    def test_event_size_is_bounded(self):
        with TemporaryDirectory() as temp:
            store = HashChainAuditStore(Path(temp) / "audit.jsonl", max_event_bytes=128)
            with self.assertRaises(AuditError):
                store.append("test", {"value": "x" * 2000})


if __name__ == "__main__":
    unittest.main()
