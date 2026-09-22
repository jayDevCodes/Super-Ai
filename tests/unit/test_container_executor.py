from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import time
import unittest

from core.runtime.container_executor import (
    AppleContainerExecutor,
    CommandResult,
    SandboxExecutionError,
)
from core.runtime.execution import ExecutionController, ExecutionPolicy, ExecutionStatus
from core.runtime.sandbox import SandboxPlan, SandboxPolicy


IMAGE_DIGEST = "sha256:" + ("a" * 64)


class FakeProcess:
    def __init__(self, runner: "FakeRunner"):
        self.runner = runner
        self._returncode = 0
        self._first_wait = True
        self._stdout = io.BytesIO(b"container-ok\n")
        self._stderr = io.BytesIO(b"")

    @property
    def returncode(self):
        return self._returncode

    def poll(self):
        if self.runner.timeout_mode and self._first_wait:
            return None
        return self._returncode

    def terminate(self):
        self.runner.terminated = True
        self._first_wait = False
        self._returncode = -15

    def kill(self):
        self.runner.killed = True
        self._first_wait = False
        self._returncode = -9

    def wait(self, timeout=None):
        if self.runner.timeout_mode and self._first_wait:
            raise subprocess.TimeoutExpired("container start", timeout)
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


class FakeRunner:
    def __init__(
        self,
        *,
        timeout_mode: bool = False,
        attestation_overrides: dict | None = None,
    ):
        self.timeout_mode = timeout_mode
        self.terminated = False
        self.killed = False
        self.calls: list[tuple[str, ...]] = []
        self.environments: list[dict[str, str]] = []
        self.process: FakeProcess | None = None
        self.fail_start = False
        self.attestation_overrides = attestation_overrides or {}
        self.ownership_labels: dict[str, str] = {}

    def run(
        self,
        command,
        *,
        cwd,
        environment,
        timeout_seconds,
    ):
        self.calls.append(command)
        self.environments.append(dict(environment))

        if command[:3] == ("container", "system", "status"):
            return self._json_result({"status": "running"})

        if command[:2] == ("container", "create"):
            self.ownership_labels = {}
            for value in command:
                if value.startswith("com.super-ai.") and "=" in value:
                    key, label_value = value.split("=", 1)
                    self.ownership_labels[key] = label_value
            return CommandResult(returncode=0, stdout=b"", stderr=b"")

        if command[:3] == ("container", "image", "inspect"):
            return self._json_result(
                [
                    {
                        "configuration": {
                            "name": "alpine:latest",
                            "descriptor": {"digest": IMAGE_DIGEST},
                        }
                    }
                ]
            )

        if command[:2] == ("container", "inspect"):
            return self._json_result(self._attestation_payload(command[-1]))

        if command[:4] == (
            "container",
            "stats",
            "--format",
            "json",
        ):
            return self._json_result(
                [
                    {
                        "id": command[-1],
                        "memoryUsageBytes": 16 * 1024 * 1024,
                        "memoryLimitBytes": 512 * 1024 * 1024,
                        "cpuUsageUsec": 1_000_000,
                        "networkRxBytes": 0,
                        "networkTxBytes": 0,
                        "blockReadBytes": 123,
                        "blockWriteBytes": 456,
                        "numProcesses": 1,
                    }
                ]
            )

        if command[:2] == ("container", "stop"):
            if self.process is not None:
                self.process.terminate()
        elif command[:2] == ("container", "kill"):
            if self.process is not None:
                self.process.kill()

        return CommandResult(returncode=0, stdout=b"", stderr=b"")

    def popen(self, command, *, cwd, environment):
        self.calls.append(command)
        self.environments.append(dict(environment))
        if self.fail_start:
            raise RuntimeError("start failed")
        self.process = FakeProcess(self)
        return self.process

    def _attestation_payload(self, container_id: str):
        configuration = {
            "id": container_id,
            "labels": dict(self.ownership_labels),
            "image": {
                "reference": "alpine:latest",
                "descriptor": {"digest": IMAGE_DIGEST},
            },
            "mounts": [
                {
                    "source": "/host/capability",
                    "destination": "/capability",
                    "options": ["ro"],
                },
                {
                    "source": "/host/output",
                    "destination": "/workspace",
                    "options": [],
                },
            ],
            "resources": {
                "cpus": 1,
                "memoryInBytes": 512 * 1024 * 1024,
            },
            "readOnly": True,
            "capDrop": ["ALL"],
            "initProcess": {
                "user": {"id": {"uid": 65532, "gid": 65532}},
                "rlimits": [
                    {"limit": "RLIMIT_NPROC", "soft": 64, "hard": 64},
                    {"limit": "RLIMIT_NOFILE", "soft": 1024, "hard": 1024},
                ],
            },
        }
        status = {"state": "created", "networks": []}
        for key, value in self.attestation_overrides.items():
            if key == "configuration":
                configuration = {**configuration, **value}
            elif key == "status":
                status = {**status, **value}
        return [{"configuration": configuration, "status": status}]

    @staticmethod
    def _json_result(payload) -> CommandResult:
        return CommandResult(
            returncode=0,
            stdout=json.dumps(payload).encode("utf-8"),
            stderr=b"",
        )


class AppleContainerExecutorTests(unittest.TestCase):
    def _plan(self, temp: str, **overrides) -> SandboxPlan:
        policy = SandboxPolicy(
            memory_mb=512,
            cpu_threads=1,
            timeout_seconds=5,
        )
        source = Path(temp) / "source"
        output = Path(temp) / "output"
        source.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        values = dict(
            backend="apple-container",
            image="alpine:latest",
            command=(
                "container",
                "run",
                "--rm",
                "--read-only",
                "--network",
                "none",
                "--no-dns",
                "alpine:latest",
                "sh",
                "-c",
                "echo ok",
            ),
            source_path=source,
            output_path=output,
            policy=policy,
            execution_ready=True,
            safety_note="network none",
        )
        values.update(overrides)
        if values["source_path"] == Path(temp):
            values["source_path"] = source
        if values["output_path"] == Path(temp):
            values["output_path"] = output
        return SandboxPlan(**values)

    def test_launch_attests_before_start_and_records_image_digest(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(
            runner=runner,
            create_timeout_seconds=2,
            control_timeout_seconds=2,
        )

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={"PATH": "/usr/bin"},
            )

            commands = runner.calls
            inspect_index = next(
                i for i, call in enumerate(commands)
                if call[:2] == ("container", "inspect")
            )
            start_index = next(
                i for i, call in enumerate(commands)
                if call[:3] == ("container", "start", "--attach")
            )
            self.assertLess(inspect_index, start_index)
            self.assertTrue(handle.attestation["passed"])
            self.assertEqual(handle.image_digest, IMAGE_DIGEST)
            handle.cleanup()

    def test_launch_rejects_process_limit_mismatch_before_start(self):
        runner = FakeRunner(
            attestation_overrides={
                "configuration": {
                    "initProcess": {
                        "rlimits": [
                            {"limit": "RLIMIT_NPROC", "soft": 32, "hard": 32},
                            {"limit": "RLIMIT_NOFILE", "soft": 1024, "hard": 1024},
                        ]
                    }
                }
            }
        )
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            with self.assertRaisesRegex(
                SandboxExecutionError,
                "RLIMIT_NPROC mismatch",
            ):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )

        self.assertFalse(
            any(call[:3] == ("container", "start", "--attach") for call in runner.calls)
        )
        self.assertTrue(
            any(call[:3] == ("container", "delete", "--force") for call in runner.calls)
        )

    def test_launch_rejects_attestation_mismatch_before_start(self):
        runner = FakeRunner(
            attestation_overrides={
                "configuration": {
                    "resources": {
                        "cpus": 2,
                        "memoryInBytes": 512 * 1024 * 1024,
                    }
                }
            }
        )
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            with self.assertRaisesRegex(
                SandboxExecutionError,
                "attestation failed",
            ):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )

        self.assertFalse(
            any(call[:3] == ("container", "start", "--attach") for call in runner.calls)
        )
        self.assertTrue(
            any(call[:3] == ("container", "delete", "--force") for call in runner.calls)
        )

    def test_launch_enforces_pinned_image_digest(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        wrong_digest = "sha256:" + ("b" * 64)
        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(
                temp,
                source_path=Path(temp),
                output_path=output,
                expected_image_digest=wrong_digest,
            )
            with self.assertRaisesRegex(SandboxExecutionError, "digest"):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )

        self.assertFalse(
            any(call[:2] == ("container", "create") for call in runner.calls)
        )

    def test_launch_creates_starts_and_cleans_container(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner, control_timeout_seconds=1)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={"PATH": "/usr/bin"},
            )

            self.assertEqual(runner.calls[0][:2], ("container", "system"))
            self.assertEqual(
                runner.calls[1][:3],
                ("container", "image", "inspect"),
            )

            create_call = next(
                call for call in runner.calls if call[:2] == ("container", "create")
            )
            self.assertIn("--network", create_call)
            self.assertIn("--ulimit", create_call)
            self.assertIn("nproc=64:64", create_call)
            self.assertIn("nofile=1024:1024", create_call)
            self.assertEqual(
                create_call[create_call.index("--network") + 1],
                "none",
            )
            self.assertNotIn("--rm", create_call)

            handle.cleanup()
            handle.cleanup()

        delete_calls = [
            call for call in runner.calls
            if call[:3] == ("container", "delete", "--force")
        ]
        self.assertEqual(len(delete_calls), 1)

    def test_timeout_requests_container_stop_and_cleanup(self):
        runner = FakeRunner(timeout_mode=True)
        executor = AppleContainerExecutor(runner=runner, control_timeout_seconds=1)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(
                temp,
                source_path=Path(temp),
                output_path=output,
                policy=SandboxPolicy(
                    memory_mb=512,
                    cpu_threads=1,
                    timeout_seconds=1,
                ),
            )
            controller = ExecutionController(sandbox_executor=executor)
            result = controller.run(
                plan,
                policy=ExecutionPolicy(
                    timeout_seconds=0.001,
                    termination_grace_seconds=0.01,
                ),
            )

        self.assertEqual(result.status, ExecutionStatus.TIMED_OUT)
        self.assertTrue(runner.terminated or runner.killed)
        self.assertTrue(
            any(call[:3] == ("container", "stop", "--signal") for call in runner.calls)
        )
        self.assertTrue(
            any(call[:3] == ("container", "delete", "--force") for call in runner.calls)
        )
        self.assertTrue(result.sandbox_attested)
        self.assertEqual(result.sandbox_image_digest, IMAGE_DIGEST)

    def test_start_failure_deletes_created_container(self):
        runner = FakeRunner()
        runner.fail_start = True
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            with self.assertRaisesRegex(SandboxExecutionError, "start failed"):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )

        self.assertTrue(
            any(call[:3] == ("container", "delete", "--force") for call in runner.calls)
        )

    def test_cleanup_refuses_unowned_container(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={"PATH": "/usr/bin"},
            )

            runner.attestation_overrides["configuration"] = {
                "labels": {
                    "com.super-ai.owner": "other-owner",
                    "com.super-ai.execution": "b" * 32,
                }
            }

            with self.assertRaisesRegex(
                SandboxExecutionError,
                "not owned",
            ):
                handle.cleanup()

            delete_calls = [
                call for call in runner.calls
                if call[:3] == ("container", "delete", "--force")
            ]
            self.assertEqual(delete_calls, [])

    def test_create_command_carries_execution_ownership_labels(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={"PATH": "/usr/bin"},
            )

            create_call = next(
                call for call in runner.calls if call[:2] == ("container", "create")
            )
            self.assertIn("com.super-ai.owner=super-ai", create_call)
            execution_labels = [
                value for value in create_call
                if value.startswith("com.super-ai.execution=")
            ]
            self.assertEqual(len(execution_labels), 1)
            self.assertEqual(
                len(execution_labels[0].split("=", 1)[1]),
                32,
            )
            handle.cleanup()

    def test_execution_controller_uses_sandbox_lifecycle_and_evidence(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(
            runner=runner,
            telemetry_interval_seconds=0.001,
        )

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={"PATH": "/usr/bin"},
            )
            time.sleep(0.01)
            handle.cleanup()

        self.assertTrue(handle.telemetry["sample_count"] >= 1)
        self.assertIn("network_activity_observed", handle.telemetry)
        self.assertFalse(handle.telemetry["network_activity_observed"])

    def test_executor_rejects_non_apple_backend(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(
                temp,
                source_path=Path(temp),
                output_path=output,
                backend="fake",
            )
            with self.assertRaisesRegex(
                SandboxExecutionError,
                "unsupported sandbox backend",
            ):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )


    def test_direct_container_executor_rejects_sensitive_environment(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            with self.assertRaisesRegex(ValueError, "sensitive environment variable"):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin", "API_KEY": "secret"},
                )

        self.assertEqual(runner.calls, [])

    def test_direct_container_executor_uses_allowlisted_environment_for_cli(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            handle = executor.launch(
                plan,
                cwd=output,
                environment={
                    "PATH": "/usr/bin",
                    "MODE": "smoke",
                },
            )
            handle.cleanup()

        self.assertTrue(runner.environments)
        for environment in runner.environments:
            self.assertEqual(environment["PATH"], "/usr/bin")
            self.assertEqual(environment["MODE"], "smoke")
            self.assertNotIn("HOME", environment)


if __name__ == "__main__":
    unittest.main()
