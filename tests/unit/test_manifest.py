import unittest

from registry.manifest import ArtifactSpec, CapabilityManifest, ManifestValidationError


class ManifestTests(unittest.TestCase):
    def test_accepts_pinned_github_source(self):
        manifest = CapabilityManifest(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields using a verified browser capability.",
            artifact=ArtifactSpec(
                repository_url="https://github.com/example/form-fill",
                pinned_ref="v1.0.0",
                sha256="a" * 64,
            ),
        )
        manifest.validate()

    def test_rejects_unpinned_source(self):
        manifest = CapabilityManifest(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields.",
            artifact=ArtifactSpec(
                repository_url="https://github.com/example/form-fill",
                pinned_ref="",
            ),
        )
        with self.assertRaises(ManifestValidationError):
            manifest.validate()

    def test_rejects_non_github_repository(self):
        artifact = ArtifactSpec(
            repository_url="https://example.com/model",
            pinned_ref="v1",
        )
        with self.assertRaisesRegex(ManifestValidationError, "github.com"):
            artifact.validate()

    def test_rejects_invalid_checksum(self):
        artifact = ArtifactSpec(
            repository_url="https://github.com/example/model",
            pinned_ref="v1",
            sha256="not-a-hash",
        )
        with self.assertRaisesRegex(ManifestValidationError, "sha256"):
            artifact.validate()


if __name__ == "__main__":
    unittest.main()
