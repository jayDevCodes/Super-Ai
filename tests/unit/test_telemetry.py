from __future__ import annotations

import json
from pathlib import Path
import unittest

from core.runtime.container_executor import CommandResult
from core.runtime.telemetry import (
    AppleContainerStatsProvider,
    ContainerStatsCollector,
    ContainerStatsSample,
    TelemetryError,
)


class FakeRunner:
    def __init__(self, payload):
        self.payload = payload

    def run(self, command, *, cwd, environment, timeout_seconds):
        return CommandResult(
            0,
            json.dumps(self.payload).encode("utf-8"),
            b"",
        )


class TelemetryTests(unittest.TestCase):
    def test_provider_parses_json_stats(self):
        runner = FakeRunner([{
            "id": "c1",
            "memoryUsageBytes": 100,
            "memoryLimitBytes": 1000,
            "cpuUsageUsec": 500,
            "networkRxBytes": 10,
            "networkTxBytes": 20,
            "blockReadBytes": 30,
            "blockWriteBytes": 40,
            "numProcesses": 2,
        }])
        provider = AppleContainerStatsProvider(
            runner,
            cwd=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
            timeout_seconds=1,
        )
        sample = provider.get_stats("c1")
        self.assertEqual(sample.memory_usage_bytes, 100)
        self.assertEqual(sample.network_tx_bytes, 20)

    def test_collector_aggregates_peak_and_cpu(self):
        class Provider:
            def __init__(self):
                self.i = 0

            def get_stats(self, container_id):
                self.i += 1
                return ContainerStatsSample(
                    timestamp_monotonic=float(self.i),
                    memory_usage_bytes=100 * self.i,
                    memory_limit_bytes=1000,
                    cpu_usage_usec=1_000_000 * self.i,
                    network_rx_bytes=10 * self.i,
                    network_tx_bytes=20 * self.i,
                    block_read_bytes=30 * self.i,
                    block_write_bytes=40 * self.i,
                    num_processes=self.i,
                )

        collector = ContainerStatsCollector(Provider())
        collector.sample("c1")
        collector.sample("c1")
        data = collector.snapshot()

        self.assertEqual(data.peak_memory_bytes, 200)
        self.assertEqual(data.peak_processes, 2)
        self.assertEqual(data.network_rx_bytes, 20)
        self.assertEqual(data.network_tx_bytes, 40)
        self.assertAlmostEqual(data.cpu_percent, 100.0)
        self.assertTrue(data.as_dict()["network_activity_observed"])

    def test_invalid_json_fails(self):
        class BadRunner:
            def run(self, command, *, cwd, environment, timeout_seconds):
                return CommandResult(0, b"bad", b"")

        provider = AppleContainerStatsProvider(
            BadRunner(),
            cwd=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
            timeout_seconds=1,
        )
        with self.assertRaisesRegex(TelemetryError, "not valid JSON"):
            provider.get_stats("c1")


if __name__ == "__main__":
    unittest.main()
