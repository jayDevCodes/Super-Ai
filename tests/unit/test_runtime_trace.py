from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.audit import HashChainAuditStore
from core.contracts import CapabilitySpec, ResourceContract, ResourceScheduler, ResourceSnapshot
from core.observability import TraceContext
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.runtime.pipeline import CapabilityExecutionRequest, CapabilityRuntime
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
            verified=True,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry=None,
        )


class RuntimeTracePropagationTests(unittest.TestCase):
    def test_supplied_trace_id_is_present_on_runtime_events(self):
        with TemporaryDirectory() as temp:
            audit = HashChainAuditStore(Path(temp) / "audit.jsonl")
            runtime = CapabilityRuntime(
                scheduler=ResourceScheduler(ResourceSnapshot(4096, 4096, 8192, 4)),
                stager=FakeStager(),
                controller=FakeController(),
                policy_engine=CapabilityPolicyEngine(
                    CapabilityPolicy(allowed_permissions=frozenset())
                ),
                audit_store=audit,
            )
            manifest = CapabilityManifest(
                "demo",
                "1.0.0",
                ArtifactSpec("https://github.com/example/demo", "a" * 40),
                "demo",
                RuntimeSpec("alpine:3.22", ("/bin/echo", "ok")),
            )
            spec = CapabilitySpec(
                "demo",
                "1.0.0",
                "demo",
                ResourceContract(256, 512),
            )
            trace = TraceContext.new_root()
            runtime.execute(
                manifest=manifest,
                capability_spec=spec,
                request=CapabilityExecutionRequest(
                    image="alpine:3.22",
                    command=("/bin/echo", "ok"),
                    output_path=Path(temp) / "out",
                    trace_context=trace,
                ),
                verifier=lambda _: True,
            )
            events = audit.read_all()
            self.assertTrue(events)
            self.assertTrue(all(
                event.attributes["trace_id"] == trace.trace_id
                for event in events
            ))
            self.assertTrue(audit.verify())


if __name__ == "__main__":
    unittest.main()
