from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.audit import HashChainAuditStore
from core.contracts import CapabilitySpec, ResourceContract, ResourceScheduler, ResourceSnapshot
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.runtime.pipeline import CapabilityExecutionRequest, CapabilityPipelineError, CapabilityRuntime
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
            stdout="ignored",
            stderr="",
            duration_seconds=0.01,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry=None,
        )


class RuntimeAuditTests(unittest.TestCase):
    def test_runtime_emits_safe_control_plane_audit_events(self):
        with TemporaryDirectory() as temp:
            audit = HashChainAuditStore(Path(temp) / "audit.jsonl")
            scheduler = ResourceScheduler(
                ResourceSnapshot(4096, 4096, 8192, 4)
            )
            runtime = CapabilityRuntime(
                scheduler=scheduler,
                stager=FakeStager(),
                controller=FakeController(),
                policy_engine=CapabilityPolicyEngine(
                    CapabilityPolicy(allowed_permissions=frozenset())
                ),
                audit_store=audit,
            )
            manifest = CapabilityManifest(
                capability_id="demo",
                version="1.0.0",
                description="demo",
                artifact=ArtifactSpec(
                    repository_url="https://github.com/example/demo",
                    pinned_commit="a" * 40,
                ),
                runtime=RuntimeSpec(
                    image="alpine:3.22",
                    command=("/bin/echo", "ok"),
                ),
            )
            spec = CapabilitySpec(
                capability_id="demo",
                version="1.0.0",
                description="demo",
                resource=ResourceContract(256, 512),
            )
            runtime.execute(
                manifest=manifest,
                capability_spec=spec,
                request=CapabilityExecutionRequest(
                    image="alpine:3.22",
                    command=("/bin/echo", "ok"),
                    output_path=Path(temp) / "out",
                    workspace_root=Path(temp),
                ),
                verifier=lambda _: True,
            )
            events = audit.read_all()
            names = [event.event_name for event in events]
            self.assertIn("runtime.execution_requested", names)
            self.assertIn("runtime.execution_started", names)
            self.assertIn("runtime.execution_finished", names)
            self.assertTrue(all("ignored" not in str(event.attributes) for event in events))
            self.assertTrue(audit.verify())


if __name__ == "__main__":
    unittest.main()
