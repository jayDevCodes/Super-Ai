from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import CapabilitySpec, ResourceContract, ResourceScheduler, ResourceSnapshot, TaskConstraints
from registry.manifest import ArtifactSpec, CapabilityManifest
from core.runtime.execution import ExecutionController, ExecutionResult, ExecutionStatus
from core.runtime.pipeline import (
    CapabilityExecutionRequest,
    CapabilityPipelineError,
    CapabilityRuntime,
)


class FakeStager:
    def __init__(self, staged):
        self.staged = staged
        self.calls = []

        class _Resolver:
            def resolve(inner_self, manifest):
                return "source-plan"

        self._resolver = _Resolver()

    def stage(self, manifest, plan, workdir):
        self.calls.append((manifest, plan, workdir))
        return self.staged


class FakeController:
    def __init__(self):
        self.calls = []

    def run(self, plan, *, policy=None, verifier=None, cleanup=None):
        self.calls.append((plan, policy, verifier))
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.01,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True if verifier else None,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry={"sample_count": 2, "network_activity_observed": False},
        )


class PipelineTests(unittest.TestCase):
    def test_end_to_end_pipeline_wires_stager_scheduler_and_controller(self):
        from core.runtime.stager import StagedArtifact

        with TemporaryDirectory() as temp:
            source_root = Path(temp) / "source"
            target = source_root / "cap"
            target.mkdir(parents=True)
            output = Path(temp) / "output"

            staged = StagedArtifact(
                capability_id="demo",
                pinned_commit="a" * 40,
                repository_root=source_root,
                target_path=target,
                downloaded_bytes=1,
                extracted_bytes=1,
                sha256="b" * 64,
            )
            stager = FakeStager(staged)
            controller = FakeController()
            scheduler = ResourceScheduler(
                ResourceSnapshot(
                    total_ram_mb=4096,
                    available_ram_mb=4096,
                    free_disk_mb=8192,
                    cpu_threads=4,
                )
            )
            runtime = CapabilityRuntime(
                scheduler=scheduler,
                stager=stager,
                controller=ExecutionController.__new__(ExecutionController),
            )

            # Replace only the controller after constructing the real runtime object.
            runtime._controller = controller

            spec = CapabilitySpec(
                capability_id="demo",
                version="1.0.0",
                description="demo capability",
                resource=ResourceContract(
                    ram_soft_mb=256,
                    ram_hard_mb=512,
                    cpu_threads=1,
                ),
                permissions=frozenset(),
            )

            manifest = CapabilityManifest(
                capability_id="demo",
                version="1.0.0",
                description="demo",
                artifact=ArtifactSpec(
                    repository_url="https://github.com/example/demo",
                    pinned_commit="a" * 40,
                ),
            )

            request = CapabilityExecutionRequest(
                image="alpine:3.22",
                command=("sh", "-c", "echo ok"),
                output_path=output,
                workspace_root=Path(temp),
                expected_image_digest="sha256:" + "a" * 64,
            )
            execution = runtime.execute(
                manifest=manifest,
                capability_spec=spec,
                request=request,
                verifier=lambda _: True,
            )

        self.assertEqual(execution.result.status, ExecutionStatus.COMPLETED)
        self.assertEqual(len(stager.calls), 1)
        self.assertEqual(controller.calls[0][0].policy.memory_mb, 512)
        self.assertEqual(controller.calls[0][0].policy.network, "disabled")
        self.assertTrue(execution.result.sandbox_attested)

    def test_network_is_disabled_without_explicit_capability_permission(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            target.mkdir()
            staged = __import__("core.runtime.stager", fromlist=["StagedArtifact"]).StagedArtifact(
                capability_id="demo",
                pinned_commit="a" * 40,
                repository_root=Path(temp),
                target_path=target,
                downloaded_bytes=1,
                extracted_bytes=1,
                sha256="b" * 64,
            )
            stager = FakeStager(staged)
            controller = FakeController()
            runtime = CapabilityRuntime(
                scheduler=ResourceScheduler(
                    ResourceSnapshot(
                        total_ram_mb=4096,
                        available_ram_mb=4096,
                        free_disk_mb=8192,
                        cpu_threads=4,
                    )
                ),
                stager=stager,
                controller=controller,
            )

            spec = CapabilitySpec(
                capability_id="demo",
                version="1.0.0",
                description="demo",
                resource=ResourceContract(256, 512),
                permissions=frozenset(),
            )

            manifest = CapabilityManifest(
                capability_id="demo",
                version="1.0.0",
                description="demo",
                artifact=ArtifactSpec(
                    repository_url="https://github.com/example/demo",
                    pinned_commit="a" * 40,
                ),
            )

            result = runtime.execute(
                manifest=manifest,
                capability_spec=spec,
                request=CapabilityExecutionRequest(
                    image="alpine:3.22",
                    command=("true",),
                    output_path=Path(temp) / "out",
                    workspace_root=Path(temp),
                ),
                task_constraints=TaskConstraints(allow_network=True),
                verifier=lambda _: True,
            )
            self.assertEqual(controller.calls[0][0].policy.network, "disabled")

    def test_request_validation_rejects_empty_command(self):
        with self.assertRaises(ValueError):
            CapabilityExecutionRequest(
                image="alpine:3.22",
                command=(),
                output_path=Path("/tmp/out"),
                workspace_root=Path("/tmp"),
            ).validate()

    def test_request_validation_requires_workspace_root(self):
        with self.assertRaises(ValueError):
            CapabilityExecutionRequest(
                image="alpine:3.22",
                command=("true",),
                output_path=Path("/tmp/out"),
                workspace_root=None,
            ).validate()


if __name__ == "__main__":
    unittest.main()
