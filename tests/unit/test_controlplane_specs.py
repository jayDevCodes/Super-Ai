import unittest

from core.controlplane.specs import RuntimeSpecGuardian
from registry.runtime import RuntimeSpec


class RuntimeSpecGuardianTests(unittest.TestCase):
    def test_review_accepts_pinned_runtime(self):
        spec = RuntimeSpec(
            image="python:3.13@sha256:" + "a" * 64,
            command=("python", "-c", "print('ok')"),
            expected_image_digest="sha256:" + "a" * 64,
            working_directory="/workspace",
        )
        review = RuntimeSpecGuardian().review(spec)
        self.assertTrue(review.accepted)
        self.assertEqual(len(review.fingerprint), 64)

    def test_review_rejects_missing_digest(self):
        spec = RuntimeSpec(
            image="python:3.13",
            command=("python", "-c", "print('ok')"),
        )
        review = RuntimeSpecGuardian().review(spec)
        self.assertFalse(review.accepted)
        self.assertIn("immutable image digest is required", review.issues)

    def test_review_rejects_outside_workdir(self):
        spec = RuntimeSpec(
            image="python:3.13@sha256:" + "b" * 64,
            command=("python",),
            expected_image_digest="sha256:" + "b" * 64,
            working_directory="/etc",
        )
        review = RuntimeSpecGuardian().review(spec)
        self.assertFalse(review.accepted)
