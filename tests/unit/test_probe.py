from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from core.runtime.container_executor import CommandResult
from core.runtime.probe import RuntimeProbe, RuntimeProbeState


class FakeRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, command, *, cwd, environment, timeout_seconds):
        self.calls.append(command)
        return self.result


class RuntimeProbeTests(unittest.TestCase):
    def test_unsupported_host_is_unavailable(self):
        runner = FakeRunner(
            CommandResult(0, b'{"status":"running"}', b"")
        )
        with patch("core.runtime.probe.platform.system", return_value="Linux"), patch(
            "core.runtime.probe.platform.machine", return_value="x86_64"
        ):
            result = RuntimeProbe(runner=runner).probe()

        self.assertEqual(result.state, RuntimeProbeState.UNAVAILABLE)
        self.assertFalse(result.available)
        self.assertEqual(runner.calls, [])

    def test_healthy_apple_silicon_is_available(self):
        runner = FakeRunner(
            CommandResult(
                0,
                json.dumps({"status": "running"}).encode("utf-8"),
                b"",
            )
        )
        with patch("core.runtime.probe.platform.system", return_value="Darwin"), patch(
            "core.runtime.probe.platform.machine", return_value="arm64"
        ), patch("core.runtime.probe.shutil.which", return_value="/usr/local/bin/container"
        ):
            result = RuntimeProbe(runner=runner).probe()

        self.assertTrue(result.available)
        self.assertEqual(result.state, RuntimeProbeState.AVAILABLE)
        self.assertEqual(
            runner.calls[0],
            ("container", "system", "status", "--format", "json"),
        )

    def test_unhealthy_service_is_degraded(self):
        runner = FakeRunner(CommandResult(1, b"", b"not ready"))
        with patch("core.runtime.probe.platform.system", return_value="Darwin"), patch(
            "core.runtime.probe.platform.machine", return_value="arm64"
        ), patch("core.runtime.probe.shutil.which", return_value="/usr/local/bin/container"
        ):
            result = RuntimeProbe(runner=runner).probe()

        self.assertEqual(result.state, RuntimeProbeState.DEGRADED)


if __name__ == "__main__":
    unittest.main()
