from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import io
import subprocess
import unittest

from core.runtime.container_executor import (
    AppleContainerExecutor,
    CommandResult,
    SandboxExecutionError,
)
from core.runtime.execution import ExecutionController, ExecutionPolicy, ExecutionStatus
from core.runtime.sandbox import AppleContainerSandbox, SandboxPlan, SandboxPolicy


class FakeProcess:
    def __init__(self, runner: "FakeRunner", *, returncode: int = 0):
        self.runner = runner
        self._returncode = returncode
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
    def __init__(self, *, timeout_mode: bool = False):
        self.timeout_mode = timeout_mode
        self.terminated = False
        self.killed = False
        self.calls: list[tuple[str, ...]] = []
        self.process: FakeProcess | None = None
        self.fail_start = False

    def run(
        self,
        command,
        *,
        cwd,
        environment,
        timeout_seconds,
    ):
        self.calls.append(command)
        if command[:2] == ("container", "stop"):
            if self.process is not None:
                self.process.terminate()
        elif command[:2] == ("container", "kill"):
            if self.process is not None:
                self.process.kill()
        return CommandResult(returncode=0, stdout=b"", stderr=b"")

    def popen(self, command, *, cwd, environment):
        self.calls.append(command)
        if self.fail_start:
            raise RuntimeError("start failed")
        self.process = FakeProcess(self)
        return self.process


class AppleContainerExecutorTests(unittest.TestCase):
    def _plan(self, temp: str, **overrides) -> SandboxPlan:
        policy = SandboxPolicy(
            memory_mb=512,
            cpu_threads=1,
            timeout_seconds=5,
        )
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
            source_path=Path(temp),
            output_path=Path(temp) / "output",
            policy=policy,
            execution_ready=True,
            safety_note="network none",
        )
        values.update(overrides)
        return SandboxPlan(**values)

    def test_launch_creates_starts_and_cleans_container(self):
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

            self.assertEqual(runner.calls[0][0:4], ("container", "create", "--name", runner.calls[0][3]))
            self.assertIn("--network", runner.calls[0])
            self.assertEqual(
                runner.calls[0][runner.calls[0].index("--network") + 1],
                "none",
            )
            self.assertNotIn("--rm", runner.calls[0])
            self.assertEqual(
                runner.calls[1][:3],
                ("container", "start", "--attach"),
            )

            handle.cleanup()
            handle.cleanup()

        delete_calls = [call for call in runner.calls if call[:3] == ("container", "delete", "--force")]
        self.assertEqual(len(delete_calls), 1)

    def test_disabled_network_plan_without_none_is_rejected(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(
                temp,
                source_path=Path(temp),
                output_path=output,
                command=("container", "run", "alpine:latest", "true"),
            )
            with self.assertRaisesRegex(
                SandboxExecutionError,
                "--network none",
            ):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )

        self.assertEqual(runner.calls, [])

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

    def test_execution_controller_uses_sandbox_lifecycle_and_releases_it(self):
        runner = FakeRunner()
        executor = AppleContainerExecutor(runner=runner)

        with TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            output.mkdir()
            plan = self._plan(temp, source_path=Path(temp), output_path=output)
            controller = ExecutionController(sandbox_executor=executor)
            result = controller.run(plan)

        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertEqual(result.stdout, "container-ok\n")
        self.assertTrue(
            any(call[:3] == ("container", "delete", "--force") for call in runner.calls)
        )

    def test_timeout_requests_container_stop_and_cleanup(self):
        runner = FakeRunner(timeout_mode=True)
        executor = AppleContainerExecutor(runner=runner)

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
            with self.assertRaisesRegex(SandboxExecutionError, "unsupported sandbox backend"):
                executor.launch(
                    plan,
                    cwd=output,
                    environment={"PATH": "/usr/bin"},
                )


if __name__ == "__main__":
    unittest.main()
