import unittest

from registry import (
    ArtifactSpec,
    CapabilityManifest,
    GitHubSourceResolver,
    ResolutionError,
)


class GitHubSourceResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = GitHubSourceResolver()

    def _manifest(self, **overrides):
        artifact = ArtifactSpec(
            repository_url=overrides.pop(
                "repository_url", "https://github.com/example/form-fill"
            ),
            pinned_commit=overrides.pop("pinned_commit", "a" * 40),
            sha256=overrides.pop("sha256", None),
            subdirectory=overrides.pop("subdirectory", "src"),
        )
        return CapabilityManifest(
            capability_id=overrides.pop("capability_id", "browser.form_fill"),
            version=overrides.pop("version", "1.0.0"),
            description=overrides.pop("description", "Fill form fields."),
            artifact=artifact,
        )

    def test_resolves_to_commit_immutable_urls(self):
        plan = self.resolver.resolve(self._manifest())

        self.assertIn("/archive/" + "a" * 40 + ".tar.gz", plan.archive_url)
        self.assertTrue(plan.clone_url.endswith("/example/form-fill.git"))
        self.assertEqual(plan.pinned_commit, "a" * 40)

    def test_partial_clone_is_pinned_and_blob_filtered(self):
        plan = self.resolver.resolve(self._manifest())

        self.assertEqual(plan.partial_clone_command[0:2], ("git", "clone"))
        self.assertIn("--filter=blob:none", plan.partial_clone_command)
        self.assertIn("--depth=1", plan.partial_clone_command)
        self.assertIn("--revision", plan.partial_clone_command)
        self.assertIn("a" * 40, plan.partial_clone_command)
        self.assertNotIn("main", plan.partial_clone_command)

    def test_sparse_checkout_targets_only_declared_subdirectory(self):
        plan = self.resolver.resolve(self._manifest(subdirectory="src/browser"))

        self.assertTrue(plan.has_sparse_target)
        self.assertEqual(plan.effective_path, "src/browser")
        self.assertEqual(
            plan.sparse_checkout_command[-1],
            "src/browser",
        )

    def test_root_capability_uses_repository_root(self):
        plan = self.resolver.resolve(self._manifest(subdirectory=""))

        self.assertFalse(plan.has_sparse_target)
        self.assertEqual(plan.effective_path, ".")
        self.assertEqual(plan.sparse_checkout_command[-1], ".")

    def test_invalid_manifest_becomes_resolution_error(self):
        manifest = self._manifest(pinned_commit="main")

        with self.assertRaises(ResolutionError):
            self.resolver.resolve(manifest)

    def test_malformed_repository_path_is_rejected(self):
        manifest = self._manifest(
            repository_url="https://github.com/example",
        )

        with self.assertRaises(ResolutionError):
            self.resolver.resolve(manifest)

    def test_query_or_fragment_is_rejected_before_resolution(self):
        manifest = self._manifest(
            repository_url="https://github.com/example/form-fill?ref=main",
        )

        with self.assertRaises(ResolutionError):
            self.resolver.resolve(manifest)


if __name__ == "__main__":
    unittest.main()
