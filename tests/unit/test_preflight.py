from __future__ import annotations

import json
from pathlib import Path
import unittest

from core.runtime.container_executor import CommandResult
from core.runtime.preflight import AppleContainerPreflight, PreflightError


DIGEST = "sha256:" + ("c" * 64)


class FakeRunner:
    def __init__(self, *, healthy=True):
        self.healthy = healthy
        self.calls = []

    def run(self, command, *, cwd, environment, timeout_seconds):
        self.calls.append(command)
        if command[:3] == ("container", "system", "status"):
            if not self.healthy:
                return CommandResult(1, b"", b"down")
            return CommandResult(0, json.dumps({"status": "running"}).encode(), b"")
        if command[:3] == ("container", "image", "inspect"):
            return CommandResult(
                0,
                json.dumps([{
                    "configuration": {
                        "name": "alpine:latest",
                        "descriptor": {"digest": DIGEST},
                    }
                }]).encode(),
                b"",
            )
        return CommandResult(1, b"", b"unexpected")


class PreflightTests(unittest.TestCase):
    def test_healthy_system_and_image_identity(self):
        runner = FakeRunner()
        preflight = AppleContainerPreflight(
            runner,
            cwd=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
        )
        status = preflight.require_healthy_system()
        identity = preflight.resolve_image("alpine:latest")

        self.assertEqual(status["status"], "running")
        self.assertEqual(identity.reference, "alpine:latest")
        self.assertEqual(identity.digest, DIGEST)

    def test_unhealthy_system_is_rejected(self):
        preflight = AppleContainerPreflight(
            FakeRunner(healthy=False),
            cwd=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
        )
        with self.assertRaisesRegex(PreflightError, "unhealthy"):
            preflight.require_healthy_system()

    def test_bad_image_json_is_rejected(self):
        runner = FakeRunner()
        runner.run = lambda *args, **kwargs: CommandResult(0, b"not-json", b"")
        preflight = AppleContainerPreflight(
            runner,
            cwd=Path("/tmp"),
            environment={"PATH": "/usr/bin"},
        )
        with self.assertRaisesRegex(PreflightError, "not valid JSON"):
            preflight.resolve_image("alpine:latest")


if __name__ == "__main__":
    unittest.main()
