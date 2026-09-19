import unittest

from core.contracts import (
    CapabilitySpec,
    ResourceContract,
    ResourceScheduler,
    ResourceSnapshot,
)
from core.contracts.scheduler import ResourceLimitError
from core.runtime import CapabilityLoader, LoadError, LoaderState
from registry.manifest import ArtifactSpec, CapabilityManifest


class FakeCapability:
    def __init__(self, spec):
        self.spec = spec
        self.cleaned = False

    def execute(self, input_data):
        return input_data

    def verify(self, input_data, output_data):
        return input_data == output_data

    def cleanup(self):
        self.cleaned = True


class CapabilityLoaderTests(unittest.TestCase):
    def setUp(self):
        self.spec = CapabilitySpec(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields.",
            resource=ResourceContract(
                ram_soft_mb=256,
                ram_hard_mb=512,
                disk_mb=32,
                cpu_threads=1,
                max_concurrency=1,
            ),
            permissions=frozenset({"browser"}),
        )
        self.manifest = CapabilityManifest(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields.",
            artifact=ArtifactSpec(
                repository_url="https://github.com/example/form-fill",
                pinned_commit="a" * 40,
            ),
        )
        self.scheduler = ResourceScheduler(
            ResourceSnapshot(
                total_ram_mb=8192,
                available_ram_mb=7000,
                free_disk_mb=1000,
                cpu_threads=4,
            )
        )

    def test_load_admits_and_unload_releases_resources(self):
        created = []

        def factory(manifest, workdir):
            created.append((manifest, workdir))
            return FakeCapability(self.spec)

        loader = CapabilityLoader(self.scheduler, factory)
        handle = loader.load(self.manifest, self.spec)

        self.assertEqual(handle.state, LoaderState.ACTIVE)
        self.assertEqual(loader.active_count, 1)
        self.assertEqual(self.scheduler.reserved_ram_mb, 512)
        self.assertTrue(handle.workdir.exists())

        loader.unload(handle)

        self.assertEqual(handle.state, LoaderState.UNLOADED)
        self.assertEqual(loader.active_count, 0)
        self.assertEqual(self.scheduler.reserved_ram_mb, 0)
        self.assertFalse(handle.workdir.exists())
        self.assertIsInstance(created[0][1], type(handle.workdir))
        self.assertTrue(created)

    def test_staging_failure_releases_resources_and_temp_storage(self):
        def factory(manifest, workdir):
            raise RuntimeError("boom")

        loader = CapabilityLoader(self.scheduler, factory)

        with self.assertRaisesRegex(LoadError, "staging failed"):
            loader.load(self.manifest, self.spec)

        self.assertEqual(self.scheduler.reserved_ram_mb, 0)
        self.assertEqual(loader.active_count, 0)

    def test_mismatched_capability_spec_is_rejected(self):
        bad_spec = CapabilitySpec(
            capability_id="browser.other",
            version="1.0.0",
            description="Different.",
            resource=self.spec.resource,
        )

        loader = CapabilityLoader(
            self.scheduler,
            lambda manifest, workdir: FakeCapability(bad_spec),
        )

        with self.assertRaisesRegex(LoadError, "capability_id"):
            loader.load(self.manifest, self.spec)

    def test_version_mismatch_is_rejected(self):
        versioned_spec = CapabilitySpec(
            capability_id=self.spec.capability_id,
            version="2.0.0",
            description="Different version.",
            resource=self.spec.resource,
        )
        loader = CapabilityLoader(
            self.scheduler,
            lambda manifest, workdir: FakeCapability(versioned_spec),
        )

        with self.assertRaisesRegex(LoadError, "version"):
            loader.load(self.manifest, self.spec)

    def test_concurrency_limit_blocks_second_load(self):
        loader = CapabilityLoader(
            self.scheduler,
            lambda manifest, workdir: FakeCapability(self.spec),
        )

        first = loader.load(self.manifest, self.spec)
        with self.assertRaises(ResourceLimitError):
            loader.load(self.manifest, self.spec)

        loader.unload(first)
        self.assertEqual(self.scheduler.reserved_ram_mb, 0)

    def test_cleanup_failure_still_releases_resources(self):
        class BrokenCleanup(FakeCapability):
            def cleanup(self):
                self.cleaned = True
                raise RuntimeError("cleanup boom")

        loader = CapabilityLoader(
            self.scheduler,
            lambda manifest, workdir: BrokenCleanup(self.spec),
        )
        handle = loader.load(self.manifest, self.spec)

        with self.assertRaisesRegex(LoadError, "cleanup failed"):
            loader.unload(handle)

        self.assertEqual(handle.state, LoaderState.UNLOADED)
        self.assertEqual(loader.active_count, 0)
        self.assertEqual(self.scheduler.reserved_ram_mb, 0)
        self.assertFalse(handle.workdir.exists())


if __name__ == "__main__":
    unittest.main()
