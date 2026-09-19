from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import threading
import time
import unittest

from core.runtime.execution import (
    ExecutionController,
    ExecutionError,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    SubprocessLauncher,
)
from core.runtime.sandbox import SandboxPlan, SandboxPolicy


class FakeStream:
    def __init__(self, payload: bytes, delay: float = 0.0):
        self.payload = payload
        self.delay = delay

    def read(self, _size: int) -> bytes:
        if self.delay:
            time.sleep(self.delay)
        payload, self.payload = self.payload, b""
        return payload


class FakeProcess:
    def __init__(self, returncode: int = 0, delay: float = 0.0, stdout=b"ok\n", stderr=b""):
        self._returncode = returncode
        self._delay = delay
        self._stdout = FakeStream(stdout, delay)
        self._stderr = FakeStream(stderr, delay)
        self.terminated = False
        self.killed = False

    @property
    def returncode(self):
        return self._returncode

    def poll(self):
        if self._delay and not self.terminated and not self.killed:
            return None
        return self._returncode

    def terminate(self):
        self.terminated = True
        self._returncode = -15

    def kill(self):
        self.killed = True
        self._returncode = -9

    def wait(self, timeout=None):
        if self._delay and not self.terminated and not self.killed:
            time.sleep(timeout or self._delay)
            raise __import__("subprocess").TimeoutExpired("fake", timeout)
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


class FakeLauncher:
    def __init__(self, process):
        self.process = process
        self.calls = []

    def launch(self, command, *, cwd, environment):
        self.calls.append((command, cwd, dict(environment)))
        return self.process


class AlwaysPassVerifier:
    def verify(self, result: ExecutionResult) -> bool:
        return True


class ExecutionControllerTests(unittest.TestCase):
    def _plan(self, **overrides):
        with TemporaryDirectory() as temp:
            pass

        policy = SandboxPolicy(
            memory_mb=512,
            cpu_threads=1,
            network="isolated",
            network_name="super-ai-internal",
        )
        values = dict(
            backend="fake",
            image="example:1",
            command=("example", "run"),
            source_path=Path("/tmp/source"),
            output_path=Path("/tmp/output"),
            policy=policy,
            execution_ready=True,
            safety_note="test",
        )
        values.update(overrides)
        return SandboxPlan(**values)

    def test_completed_process_returns_bounded_result(self):
        process = FakeProcess(returncode=0, stdout=b"hello\n", stderr=b"")
        launcher = FakeLauncher(process)
        controller = ExecutionController(
            launcher=launcher,
            environment={"SUPER_AI_TEST": "1"},
        )

        with TemporaryDirectory() as temp:
            plan = self._plan(
                source_path=Path(temp),
                output_path=Path(temp),
            )

            cleanup_called = []
            result = controller.run(
                plan,
                verifier=AlwaysPassVerifier(),
                cleanup=lambda: cleanup_called.append(True),
            )

        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "hello\n")
        self.assertTrue(result.verified)
        self.assertTrue(result.cleanup_completed)
        self.assertEqual(cleanup_called, [True])
        self.assertEqual(launcher.calls[0][2]["SUPER_AI_TEST"], "1")

    def test_nonzero_process_is_failed(self):
        process = FakeProcess(returncode=7)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            result = controller.run(plan)

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(result.exit_code, 7)

    def test_output_is_hard_bounded_in_memory(self):
        process = FakeProcess(stdout=b"x" * 128)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            result = controller.run(
                plan,
                policy=ExecutionPolicy(
                    timeout_seconds=1,
                    max_output_bytes=16,
                    max_error_bytes=16,
                ),
            )

        self.assertEqual(len(result.stdout.encode("utf-8")), 16)
        self.assertTrue(result.stdout_truncated)

    def test_verification_failure_changes_status(self):
        class RejectVerifier:
            def verify(self, result):
                return False

        process = FakeProcess(returncode=0)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            result = controller.run(plan, verifier=RejectVerifier())

        self.assertEqual(result.status, ExecutionStatus.VERIFICATION_FAILED)
        self.assertFalse(result.verified)

    def test_cleanup_failure_is_reported(self):
        process = FakeProcess(returncode=0)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))

            def broken_cleanup():
                raise RuntimeError("cleanup")

            result = controller.run(plan, cleanup=broken_cleanup)

        self.assertEqual(result.status, ExecutionStatus.CLEANUP_FAILED)
        self.assertFalse(result.cleanup_completed)

    def test_cleanup_runs_after_timeout(self):
        process = FakeProcess(returncode=0, delay=0.05)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            cleanup_called = threading.Event()
            result = controller.run(
                plan,
                policy=ExecutionPolicy(
                    timeout_seconds=0.001,
                    max_output_bytes=32,
                    max_error_bytes=32,
                    termination_grace_seconds=0.01,
                ),
                cleanup=cleanup_called.set,
            )

        self.assertEqual(result.status, ExecutionStatus.TIMED_OUT)
        self.assertTrue(process.terminated or process.killed)
        self.assertTrue(cleanup_called.is_set())

    def test_no_backend_is_refused(self):
        controller = ExecutionController()

        with TemporaryDirectory() as temp:
            plan = self._plan(
                source_path=Path(temp),
                output_path=Path(temp),
            )
            with self.assertRaisesRegex(ExecutionError, "no execution backend"):
                controller.run(plan)

    def test_not_execution_ready_is_refused(self):
        process = FakeProcess()
        launcher = FakeLauncher(process)
        controller = ExecutionController(launcher)

        with TemporaryDirectory() as temp:
            plan = self._plan(
                source_path=Path(temp),
                output_path=Path(temp),
                execution_ready=False,
            )
            with self.assertRaisesRegex(ExecutionError, "execution-ready"):
                controller.run(plan)

        self.assertEqual(launcher.calls, [])

    def test_verifier_exception_fails_closed_and_cleanup_runs(self):
        process = FakeProcess(returncode=0)
        launcher = FakeLauncher(process)
        controller = ExecutionController(launcher)

        class BrokenVerifier:
            def verify(self, result):
                raise RuntimeError("verifier boom")

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            cleanup_called = threading.Event()
            result = controller.run(
                plan,
                verifier=BrokenVerifier(),
                cleanup=cleanup_called.set,
            )

        self.assertEqual(result.status, ExecutionStatus.VERIFICATION_FAILED)
        self.assertFalse(result.verified)
        self.assertTrue(result.cleanup_completed)
        self.assertTrue(cleanup_called.is_set())

    def test_launch_failure_still_runs_cleanup(self):
        class BrokenLauncher:
            def launch(self, command, *, cwd, environment):
                raise RuntimeError("launch boom")

        controller = ExecutionController(BrokenLauncher())

        with TemporaryDirectory() as temp:
            plan = self._plan(source_path=Path(temp), output_path=Path(temp))
            cleanup_called = threading.Event()
            with self.assertRaisesRegex(RuntimeError, "launch boom"):
                controller.run(plan, cleanup=cleanup_called.set)
            self.assertTrue(cleanup_called.is_set())

    def test_controller_cannot_extend_sandbox_timeout(self):
        process = FakeProcess(returncode=0)
        controller = ExecutionController(FakeLauncher(process))

        with TemporaryDirectory() as temp:
            plan = self._plan(
                source_path=Path(temp),
                output_path=Path(temp),
                policy=SandboxPolicy(
                    memory_mb=512,
                    cpu_threads=1,
                    network="isolated",
                    network_name="super-ai-internal",
                    timeout_seconds=1,
                ),
            )
            with self.assertRaisesRegex(ExecutionError, "exceed"):
                controller.run(
                    plan,
                    policy=ExecutionPolicy(timeout_seconds=2),
                )

    def test_real_subprocess_launcher_uses_stream_attributes(self):
        controller = ExecutionController(launcher=SubprocessLauncher())

        with TemporaryDirectory() as temp:
            plan = self._plan(
                source_path=Path(temp),
                output_path=Path(temp),
                command=(
                    sys.executable,
                    "-c",
                    "print('real-subprocess-ok')",
                ),
            )
            result = controller.run(plan)

        self.assertEqual(result.status, ExecutionStatus.COMPLETED)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("real-subprocess-ok", result.stdout)

    def test_policy_validation_rejects_zero_output_limit(self):
        with self.assertRaises(ValueError):
            ExecutionPolicy(max_output_bytes=0).validate()



if __name__ == "__main__":
    unittest.main()
