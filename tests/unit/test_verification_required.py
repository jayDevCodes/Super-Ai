from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.contracts import CapabilitySpec, ResourceContract, ResourceScheduler, ResourceSnapshot
from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.runtime.pipeline import (
    CapabilityExecutionRequest,
    CapabilityPipelineError,
    CapabilityRuntime,
)
from core.runtime.stager import StagedArtifact
from registry.manifest import ArtifactSpec, CapabilityManifest
from registry.runtime import RuntimeSpec


class FakeStager:
    def stage(self, manifest, plan, workdir):
        target = Path(workdir) / "cap"
        target.mkdir()
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
    def run(self, plan, *, policy=None, verifier=None, cleanup=None):
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="",
            stderr="",
            duration_seconds=0.01,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True if verifier else None,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry=None,
        )


class VerificationRequirementTests(unittest.TestCase):
    def runtime(self):
        return CapabilityRuntime(
            scheduler=ResourceScheduler(
                ResourceSnapshot(4096, 4096, 8192, 4)
            ),
            stager=FakeStager(),
            controller=FakeController(),
        )

    def manifest(self):
        return CapabilityManifest(
            capability_id="demo",
            version="1.0.0",
            description="demo",
            artifact=ArtifactSpec(
                "https://github.com/example/demo",
                "a" * 40,
            ),
            runtime=RuntimeSpec("alpine:3.22", ("/bin/echo", "ok")),
        )

    def spec(self, required=True):
        return CapabilitySpec(
            capability_id="demo",
            version="1.0.0",
            description="demo",
            resource=ResourceContract(256, 512),
            verification_required=required,
        )

    def request(self, temp):
        return CapabilityExecutionRequest(
            image="alpine:3.22",
            command=("/bin/echo", "ok"),
            output_path=Path(temp) / "out",
            workspace_root=Path(temp),
        )

    def test_required_verification_is_enforced_before_staging(self):
        runtime = self.runtime()
        with TemporaryDirectory() as temp:
            with self.assertRaises(CapabilityPipelineError):
                runtime.execute(
                    manifest=self.manifest(),
                    capability_spec=self.spec(required=True),
                    request=self.request(temp),
                )

    def test_optional_verification_can_run_without_verifier(self):
        runtime = self.runtime()
        with TemporaryDirectory() as temp:
            result = runtime.execute(
                manifest=self.manifest(),
                capability_spec=self.spec(required=False),
                request=self.request(temp),
            )
        self.assertIsNone(result.result.verified)


if __name__ == "__main__":
    unittest.main()
