import unittest

from core.supplychain.telemetry import SupplyChainTelemetry


class SupplyChainTelemetryTests(unittest.TestCase):
    def test_snapshot(self):
        t=SupplyChainTelemetry()
        t.record_admission(True)
        t.record_admission(False)
        t.record_verification(True)
        t.record_sync()
        self.assertEqual(t.snapshot().admitted,1)
        self.assertEqual(t.snapshot().rejected,1)
        self.assertEqual(t.snapshot().verified,1)
        self.assertEqual(t.snapshot().registry_syncs,1)
