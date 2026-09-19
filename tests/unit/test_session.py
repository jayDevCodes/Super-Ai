from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from core.contracts import ResourceBudget, ResourceContract, ResourceScheduler, ResourceSnapshot
from core.runtime.execution import ExecutionController, ExecutionPolicy
from core.runtime.sandbox import SandboxPlan, SandboxPolicy
from core.runtime.session import ExecutionSession, ExecutionSessionError


class FakeStream:
    def __init__(self, payload=b"ok\n"):
        self.payload = payload

    def read(self, _size):
        payload, self.payload = self.payload, b""
        return payload


class FakeProcess:
    def __init__(self, returncode=0):
        self._returncode = returncode
        self._stdout = FakeStream()
        self._stderr = FakeStream()

    def poll(self):
        return self._returncode

    def terminate(self):
        self._returncode = -15

    def kill(self):
        self._returncode = -9

    def wait(self, timeout=None):
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


class FakeLauncher:
    def __init__(self):
        self.calls = []

    def launch(self, command, *, cwd, environment):
        self.calls.append((command, cwd, dict(environment)))
        return FakeProcess()


class ExecutionSessionTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = ResourceScheduler(
            ResourceSnapshot(
                total_ram_mb=8192,
                available_ram_mb=7000,
                free_disk_mb=10000,
                cpu_threads=4,
            ),
            ResourceBudget(
                system_reserved_ram_mb=2000,
                control_plane_reserved_ram_mb=700,
                safety_reserve_ram_mb=700,
                max_parallel_workers=4,
            ),
        )
        self.contract = ResourceContract(
            ram_soft_mb=128,
            ram_hard_mb=256,
            disk_mb=32,
            cpu_threads=1,
            max_concurrency=1,
        )
        self.controller = ExecutionController(FakeLauncher())

    def _plan(self, temp):
        policy = SandboxPolicy(
            memory_mb=512,
            cpu_threads=1,
            network="isolated",
            network_name="super-ai-internal",
            timeout_seconds=5,
        )
        return SandboxPlan(
            backend="fake",
            image="example:1",
            command=("example", "run"),
            source_path=Path(temp),
            output_path=Path(temp),
            policy=policy,
            execution_ready=True,
        )

    def test_session_holds_and_releases_resources(self):
        with TemporaryDirectory() as temp:
            with ExecutionSession(
                self.scheduler,
                self.controller,
                capability_id="demo.capability",
                resource=self.contract,
            ) as session:
                self.assertTrue(session.active)
                self.assertEqual(self.scheduler.reserved_ram_mb, 256)
                result = session.run(self._plan(temp))
                self.assertEqual(result.exit_code, 0)

        self.assertFalse(session.active)
        self.assertEqual(self.scheduler.reserved_ram_mb, 0)

    def test_exception_still_releases_resources(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises(ExecutionSessionError):
                with ExecutionSession(
                    self.scheduler,
                    self.controller,
                    capability_id="demo.capability",
                    resource=self.contract,
                ) as session:
                    self.assertEqual(self.scheduler.reserved_ram_mb, 256)
                    raise ExecutionSessionError("boom")

        self.assertEqual(self.scheduler.reserved_ram_mb, 0)

    def test_run_requires_active_session(self):
        with TemporaryDirectory() as temp:
            session = ExecutionSession(
                self.scheduler,
                self.controller,
                capability_id="demo.capability",
                resource=self.contract,
            )
            with self.assertRaisesRegex(ExecutionSessionError, "not active"):
                session.run(self._plan(temp))

    def test_run_requires_one_execution(self):
        with TemporaryDirectory() as temp:
            with ExecutionSession(
                self.scheduler,
                self.controller,
                capability_id="demo.capability",
                resource=self.contract,
            ) as session:
                session.run(self._plan(temp))
                with self.assertRaisesRegex(ExecutionSessionError, "only once"):
                    session.run(self._plan(temp))

    def test_cleanup_error_still_releases_lease(self):
        with TemporaryDirectory() as temp:
            with ExecutionSession(
                self.scheduler,
                self.controller,
                capability_id="demo.capability",
                resource=self.contract,
            ) as session:
                result = session.run(
                    self._plan(temp),
                    policy=ExecutionPolicy(timeout_seconds=1),
                    cleanup=lambda: (_ for _ in ()).throw(RuntimeError("cleanup")),
                )
                self.assertEqual(result.status.value, "cleanup_failed")

        self.assertEqual(self.scheduler.reserved_ram_mb, 0)


if __name__ == "__main__":
    unittest.main()
