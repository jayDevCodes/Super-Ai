from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import WorkspaceContract
from core.runtime.sandbox import AppleContainerSandbox, SandboxError, SandboxPolicy


class AppleContainerSandboxTests(unittest.TestCase):
    def _dirs(self):
        temp = TemporaryDirectory()
        root = Path(temp.name)
        source = root / "source"
        output = root / "output"
        source.mkdir()
        output.mkdir()
        return temp, source, output

    def test_default_policy_is_execution_ready_with_network_none(self):
        temp, source, output = self._dirs()
        with temp:
            plan = AppleContainerSandbox().build_plan(
                image="python:3.13-slim",
                command=("python", "-c", "print('ok')"),
                source_path=source,
                output_path=output,
                policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
            )
            self.assertTrue(plan.execution_ready)
            self.assertIn("--read-only", plan.command)
            self.assertIn("--cap-drop", plan.command)
            self.assertIn("ALL", plan.command)
            self.assertIn("--rm", plan.command)
            self.assertIn("--memory", plan.command)
            self.assertIn("512M", plan.command)
            self.assertTrue(any("/capability" in item for item in plan.command))
            self.assertTrue(any("/workspace" in item for item in plan.command))
            self.assertIn("network none", plan.safety_note.lower())
            self.assertEqual(
                plan.command[plan.command.index("--network") + 1],
                "none",
            )
            self.assertIn("--no-dns", plan.command)


    def test_plan_carries_workspace_contract(self):
        temp, source, output = self._dirs()
        with temp:
            contract = WorkspaceContract(
                root=Path(temp.name),
                source_path=source,
                output_path=output,
            )
            plan = AppleContainerSandbox().build_plan(
                image="alpine:3.22",
                command=("true",),
                source_path=source,
                output_path=output,
                policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                workspace=contract,
            )
            self.assertIs(plan.workspace, contract)
            plan.workspace.validate(require_output=True)

    def test_workspace_contract_paths_must_match_plan_paths(self):
        temp, source, output = self._dirs()
        with temp:
            other = Path(temp.name) / "other"
            other.mkdir()
            contract = WorkspaceContract(
                root=Path(temp.name),
                source_path=other,
                output_path=output,
            )
            with self.assertRaisesRegex(
                SandboxError,
                "workspace contract paths",
            ):
                AppleContainerSandbox().build_plan(
                    image="alpine:3.22",
                    command=("true",),
                    source_path=source,
                    output_path=output,
                    policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                    workspace=contract,
                )

    def test_isolated_network_requires_named_network(self):
        temp, source, output = self._dirs()
        with temp:
            policy = SandboxPolicy(
                memory_mb=512,
                cpu_threads=1,
                network="isolated",
                network_name="super-ai-internal",
            )
            plan = AppleContainerSandbox().build_plan(
                image="alpine:latest",
                command=("true",),
                source_path=source,
                output_path=output,
                policy=policy,
            )
            self.assertTrue(plan.execution_ready)
            self.assertEqual(
                plan.command[plan.command.index("--network") + 1],
                "super-ai-internal",
            )

    def test_source_and_output_must_be_distinct(self):
        temp = TemporaryDirectory()
        with temp:
            root = Path(temp.name)
            shared = root / "shared"
            shared.mkdir()
            with self.assertRaisesRegex(SandboxError, "different"):
                AppleContainerSandbox().build_plan(
                    image="alpine:latest",
                    command=("true",),
                    source_path=shared,
                    output_path=shared,
                    policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                )

    def test_missing_directories_are_rejected(self):
        temp = TemporaryDirectory()
        with temp:
            root = Path(temp.name)
            with self.assertRaisesRegex(SandboxError, "source_path"):
                AppleContainerSandbox().build_plan(
                    image="alpine:latest",
                    command=("true",),
                    source_path=root / "missing",
                    output_path=root,
                    policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                )

    def test_empty_command_is_rejected(self):
        temp, source, output = self._dirs()
        with temp:
            with self.assertRaisesRegex(SandboxError, "command"):
                AppleContainerSandbox().build_plan(
                    image="alpine:latest",
                    command=(),
                    source_path=source,
                    output_path=output,
                    policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                )

    def test_policy_validation_rejects_unknown_network_mode(self):
        with self.assertRaises(ValueError):
            SandboxPolicy(memory_mb=512, cpu_threads=1, network="internet").validate()

    def test_enabled_network_requires_named_network(self):
        with self.assertRaises(ValueError):
            SandboxPolicy(
                memory_mb=512, cpu_threads=1, network="enabled", network_name=None
            ).validate()

    def test_unsafe_image_is_rejected(self):
        temp, source, output = self._dirs()
        with temp:
            with self.assertRaises(SandboxError):
                AppleContainerSandbox().build_plan(
                    image="alpine latest",
                    command=("true",),
                    source_path=source,
                    output_path=output,
                    policy=SandboxPolicy(memory_mb=512, cpu_threads=1),
                )


if __name__ == "__main__":
    unittest.main()
