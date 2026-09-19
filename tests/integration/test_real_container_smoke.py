from __future__ import annotations

import os
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
import unittest

from core.contracts import ResourceScheduler
from core.runtime import (
    AppleContainerExecutor,
    CapabilitySmokeTest,
    ExecutionController,
    ExecutionStatus,
    RuntimeProbe,
    StageError,
    StagedArtifact,
)


_RUN_REAL = os.environ.get("SUPER_AI_RUN_APPLE_CONTAINER_INTEGRATION") == "1"


@unittest.skipUnless(
    _RUN_REAL,
    "set SUPER_AI_RUN_APPLE_CONTAINER_INTEGRATION=1 on a real Apple Silicon Mac",
)
class AppleContainerRealRuntimeTests(unittest.TestCase):
    def test_staged_capability_security_smoke(self):
        image = os.environ.get("SUPER_AI_SMOKE_IMAGE", "alpine:3.22")
        expected_digest = os.environ.get("SUPER_AI_SMOKE_IMAGE_DIGEST")

        with TemporaryDirectory() as temp:
            root = Path(temp)
            capability = root / "capability"
            capability.mkdir()
            marker = capability / "marker.txt"
            marker.write_text("smoke", encoding="utf-8")
            marker.chmod(0o644)

            secret = root / "host-secret.txt"
            secret.write_text("must-stay-on-host", encoding="utf-8")
            secret.chmod(0o600)

            script = capability / "smoke.sh"
            script.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                '[ "$(id -u)" = "65532" ]\n'
                "test -r /capability/marker.txt\n"
                'if printf x > /capability/write-probe 2>/dev/null; then exit 10; fi\n'
                'if [ -e /etc/super-ai-host-write-probe ]; then exit 11; fi\n'
                'if [ -e "' + shlex.quote(str(secret)) + '" ]; then exit 12; fi\n'
                'if wget -q -T 2 -O /dev/null https://example.com 2>/dev/null; then exit 13; fi\n'
                "printf '%s\\n' SUPER_AI_SMOKE_OK\n"
                "printf '%s\\n' smoke > /workspace/smoke-output.txt\n",
                encoding="utf-8",
            )
            script.chmod(0o755)

            source = root / "source-root"
            source.mkdir()
            staged_target = source / "runtime"
            staged_target.mkdir()
            for item in capability.iterdir():
                target = staged_target / item.name
                if item.is_file():
                    target.write_bytes(item.read_bytes())
                    target.chmod(item.stat().st_mode & 0o777)
            staged = StagedArtifact(
                capability_id="smoke-capability",
                pinned_commit="a" * 40,
                repository_root=source,
                target_path=staged_target,
                downloaded_bytes=0,
                extracted_bytes=sum(
                    p.stat().st_size for p in staged_target.rglob("*") if p.is_file()
                ),
                sha256="a" * 64,
            )
            output = root / "output"

            probe = RuntimeProbe().probe()
            if not probe.available:
                self.skipTest(probe.reason)

            # A user running the smoke test can either pre-pull the image or use
            # a mutable tag and allow the executor's preflight to resolve its
            # current immutable local digest.
            scheduler = ResourceScheduler(
                total_ram_mb=4096,
                total_disk_mb=8192,
                total_cpu_threads=4,
                max_parallel_workers=1,
            )
            executor = AppleContainerExecutor()
            controller = ExecutionController(sandbox_executor=executor)
            smoke = CapabilitySmokeTest(
                scheduler=scheduler,
                controller=controller,
            )

            result = smoke.run(
                staged,
                image=image,
                expected_image_digest=expected_digest,
                command=("/bin/sh", "/capability/smoke.sh"),
                output_path=output,
                verifier=lambda execution: (
                    execution.status is ExecutionStatus.COMPLETED
                    and "SUPER_AI_SMOKE_OK" in execution.stdout
                ),
            )

            self.assertTrue(result.passed, result.invariant_failures)
            self.assertTrue((output / "smoke-output.txt").exists())


if __name__ == "__main__":
    unittest.main()
