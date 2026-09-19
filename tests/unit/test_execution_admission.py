import unittest

from core.runtime.admission import ExecutionAdmissionGate
from registry.runtime import RuntimeSpec


class ExecutionAdmissionTests(unittest.TestCase):
    def test_pinned_runtime_and_secure_profile_are_admitted(self):
        digest = "a" * 64
        spec = RuntimeSpec(
            image="python:3.13@sha256:" + digest,
            command=("python", "-c", "print('ok')"),
            expected_image_digest="sha256:" + digest,
            working_directory="/workspace",
        )
        decision = ExecutionAdmissionGate().evaluate(spec)
        self.assertTrue(decision.accepted)
        self.assertEqual(len(decision.evidence_fingerprints), 2)

    def test_external_artifact_requirement_fails_closed(self):
        digest = "b" * 64
        spec = RuntimeSpec(
            image="python:3.13@sha256:" + digest,
            command=("python",),
            expected_image_digest="sha256:" + digest,
        )
        decision = ExecutionAdmissionGate().evaluate(spec, require_artifact=True)
        self.assertFalse(decision.accepted)
        self.assertIn("external artifact evidence is required", decision.reasons)
