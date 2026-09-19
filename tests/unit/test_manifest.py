import unittest

from registry.manifest import ArtifactSpec, CapabilityManifest, ManifestValidationError


class ManifestTests(unittest.TestCase):
    def _manifest(self, **artifact_overrides):
        artifact_values = {
            "repository_url": "https://github.com/example/form-fill",
            "pinned_commit": "a" * 40,
        }
        artifact_values.update(artifact_overrides)
        return CapabilityManifest(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields using a verified browser capability.",
            artifact=ArtifactSpec(**artifact_values),
        )

    def test_accepts_https_github_source_pinned_to_commit(self):
        self._manifest(sha256="a" * 64).validate()

    def test_rejects_moving_or_missing_reference(self):
        with self.assertRaises(ManifestValidationError):
            self._manifest(pinned_commit="v1.0.0").validate()

    def test_rejects_non_github_repository(self):
        with self.assertRaisesRegex(ManifestValidationError, "github.com"):
            self._manifest(
                repository_url="https://example.com/model"
            ).validate()

    def test_rejects_query_or_fragment_on_repository_url(self):
        with self.assertRaises(ManifestValidationError):
            self._manifest(
                repository_url="https://github.com/example/model?ref=main"
            ).validate()

    def test_rejects_invalid_checksum(self):
        with self.assertRaisesRegex(ManifestValidationError, "sha256"):
            self._manifest(sha256="not-a-hash").validate()

    def test_rejects_path_traversal_in_subdirectory(self):
        with self.assertRaises(ManifestValidationError):
            self._manifest(subdirectory="../outside").validate()


if __name__ == "__main__":
    unittest.main()
