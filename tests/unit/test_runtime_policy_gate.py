from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import CapabilitySpec, ResourceContract, ResourceScheduler, ResourceSnapshot, TaskConstraints
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.runtime.pipeline import CapabilityExecutionRequest, CapabilityPipelineError, CapabilityRuntime
from core.runtime.stager import StagedArtifact
from registry.manifest import ArtifactSpec, CapabilityManifest
from registry.runtime import RuntimeSpec


class FakeStager:
    def __init__(self):
        self._resolver = None
        self.calls = []

    def stage(self, manifest, plan, workdir):
        self.calls.append(manifest.capability_id)
        target = Path(workdir) / "cap"
        target.mkdir(parents=True, exist_ok=True)
        return StagedArtifact(
            capability_id=manifest.capability_id,
            pinned_commit="a" * 40,
            repository_root=Path(workdir),
            target_path=target,
            downloaded_bytes=1,
            extracted_bytes=1,
            sha256="b" * 64,
        )


class FakeController:
    def __init__(self):
        self.calls = []

    def run(self, plan, *, policy=None, verifier=None, cleanup=None):
        self.calls.append(plan)
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.01,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry={"network_activity_observed": False},
        )


def manifest():
    return CapabilityManifest(
        capability_id="demo",
        version="1.0.0",
        description="demo",
        artifact=ArtifactSpec(
            repository_url="https://github.com/example/demo",
            pinned_commit="a" * 40,
        ),
        runtime=RuntimeSpec(
            image="alpine:3.22",
            command=("/bin/sh", "-c", "echo ok"),
        ),
    )


def spec(*permissions):
    return CapabilitySpec(
        capability_id="demo",
        version="1.0.0",
        description="demo",
        resource=ResourceContract(256, 512),
        permissions=frozenset(permissions),
    )


class RuntimePolicyGateTests(unittest.TestCase):
    def runtime(self, allowed):
        scheduler = ResourceScheduler(
            ResourceSnapshot(
                total_ram_mb=4096,
                available_ram_mb=4096,
                free_disk_mb=8192,
                cpu_threads=4,
            )
        )
        controller = FakeController()
        runtime = CapabilityRuntime(
            scheduler=scheduler,
            stager=FakeStager(),
            controller=controller,
            policy_engine=CapabilityPolicyEngine(
                CapabilityPolicy(allowed_permissions=frozenset(allowed))
            ),
        )
        return runtime, controller

    def test_runtime_rechecks_policy_before_staging(self):
        runtime, controller = self.runtime({"browser"})
        with TemporaryDirectory() as temp:
            with self.assertRaises(CapabilityPipelineError):
                runtime.execute(
                    manifest=manifest(),
                    capability_spec=spec("filesystem"),
                    request=CapabilityExecutionRequest(
                        image="alpine:3.22",
                        command=("/bin/sh",),
                        output_path=Path(temp) / "out",
                        workspace_root=Path(temp),
                    ),
                )

    def test_network_is_taken_from_policy_decision(self):
        runtime, controller = self.runtime({"network"})
        with TemporaryDirectory() as temp:
            runtime.execute(
                manifest=manifest(),
                capability_spec=spec("network"),
                request=CapabilityExecutionRequest(
                    image="alpine:3.22",
                    command=("/bin/sh",),
                    output_path=Path(temp) / "out",
                    workspace_root=Path(temp),
                ),
                task_constraints=TaskConstraints(allow_network=True),
                verifier=lambda _: True,
            )
        self.assertEqual(controller.calls[0].policy.network, "enabled")


if __name__ == "__main__":
    unittest.main()
