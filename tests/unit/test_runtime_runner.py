from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.brain.runtime_runner import (
    CapabilityRuntimeStepRunner,
    RuntimeRunnerError,
)
from core.contracts import CapabilitySpec, ResourceContract
from core.policy import PolicyDecisionState
from core.router import RouteCandidate
from core.runtime.execution import ExecutionResult, ExecutionStatus
from core.runtime.pipeline import CapabilityExecution
from core.runtime.stager import StagedArtifact
from registry.catalog import RegistryEntry
from registry.manifest import ArtifactSpec, CapabilityManifest
from registry.runtime import RuntimeSpec


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        spec = kwargs["capability_spec"]
        artifact = StagedArtifact(
            capability_id=spec.capability_id,
            pinned_commit="a" * 40,
            repository_root=Path("/tmp"),
            target_path=Path("/tmp/capability"),
            downloaded_bytes=1,
            extracted_bytes=1,
            sha256="b" * 64,
        )
        result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.1,
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
            verified=True,
            cleanup_completed=True,
            sandbox_attested=True,
            sandbox_image_digest="sha256:" + "a" * 64,
            telemetry={"network_activity_observed": False},
        )
        return CapabilityExecution(result=result, staged=artifact)


def make_route(runtime_spec: RuntimeSpec | None):
    manifest = CapabilityManifest(
        capability_id="demo",
        version="1.0.0",
        description="demo",
        artifact=ArtifactSpec(
            repository_url="https://github.com/example/demo",
            pinned_commit="a" * 40,
        ),
        runtime=runtime_spec,
    )
    spec = CapabilitySpec(
        capability_id="demo",
        version="1.0.0",
        description="demo",
        resource=ResourceContract(256, 512),
    )
    return RouteCandidate(
        entry=RegistryEntry(manifest=manifest, spec=spec),
        score=1,
        reasons=(),
        policy_state=PolicyDecisionState.ALLOW,
        policy_reasons=(),
    )


class RuntimeRunnerTests(unittest.TestCase):
    def test_runtime_spec_is_forwarded(self):
        runtime = FakeRuntime()
        with TemporaryDirectory() as temp:
            runner = CapabilityRuntimeStepRunner(
                runtime=runtime,
                workspace_root=Path(temp),
            )
            result = runner.run(
                make_route(
                    RuntimeSpec(
                        image="alpine:3.22",
                        command=("/bin/echo", "ok"),
                        expected_image_digest="sha256:" + "a" * 64,
                    )
                ),
                step=object(),
                context={},
            )
        self.assertEqual(result.version, "1.0.0")
        self.assertEqual(runtime.calls[0]["request"].image, "alpine:3.22")
        self.assertEqual(runtime.calls[0]["request"].command, ("/bin/echo", "ok"))
        self.assertEqual(
            runtime.calls[0]["request"].expected_image_digest,
            "sha256:" + "a" * 64,
        )

    def test_missing_runtime_spec_fails_closed(self):
        runtime = FakeRuntime()
        with TemporaryDirectory() as temp:
            runner = CapabilityRuntimeStepRunner(
                runtime=runtime,
                workspace_root=Path(temp),
            )
            with self.assertRaises(RuntimeRunnerError):
                runner.run(make_route(None), step=object(), context={})


if __name__ == "__main__":
    unittest.main()
