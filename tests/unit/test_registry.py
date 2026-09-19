from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from core.contracts import CapabilitySpec, ResourceContract
from registry.catalog import CapabilityRegistry, RegistryEntry, RegistryError
from registry.manifest import ArtifactSpec, CapabilityManifest


def make_entry(capability_id="browser.read", version="1.0.0", permission="browser"):
    manifest = CapabilityManifest(
        capability_id=capability_id,
        version=version,
        description="Read browser state",
        artifact=ArtifactSpec(
            repository_url="https://github.com/example/capability",
            pinned_commit="a" * 40,
        ),
    )
    spec = CapabilitySpec(
        capability_id=capability_id,
        version=version,
        description="Read browser state",
        resource=ResourceContract(256, 512),
        permissions=frozenset({permission}),
    )
    return RegistryEntry(manifest=manifest, spec=spec)


class CapabilityRegistryTests(unittest.TestCase):
    def test_register_and_get_is_version_aware(self):
        registry = CapabilityRegistry([make_entry(version="1.0.0"), make_entry(version="2.0.0")])
        with self.assertRaises(RegistryError):
            registry.get("browser.read")
        self.assertEqual(registry.get("browser.read", "2.0.0").manifest.version, "2.0.0")

    def test_search_is_deterministic_and_filterable(self):
        registry = CapabilityRegistry([
            make_entry("z.capability", "1.0.0", "filesystem"),
            make_entry("a.capability", "1.0.0", "browser"),
        ])
        results = registry.search(permission="browser")
        self.assertEqual([x.manifest.capability_id for x in results], ["a.capability"])

    def test_duplicate_registration_is_rejected(self):
        registry = CapabilityRegistry([make_entry()])
        with self.assertRaises(RegistryError):
            registry.register(make_entry())

    def test_json_registry_round_trip(self):
        entry = make_entry()
        payload = {
            "capabilities": [{
                "manifest": {
                    "capability_id": entry.manifest.capability_id,
                    "version": entry.manifest.version,
                    "description": entry.manifest.description,
                    "artifact": {
                        "repository_url": entry.manifest.artifact.repository_url,
                        "pinned_commit": entry.manifest.artifact.pinned_commit,
                    },
                },
                "spec": {
                    "capability_id": entry.spec.capability_id,
                    "version": entry.spec.version,
                    "description": entry.spec.description,
                    "permissions": sorted(entry.spec.permissions),
                    "resource": {
                        "ram_soft_mb": entry.spec.resource.ram_soft_mb,
                        "ram_hard_mb": entry.spec.resource.ram_hard_mb,
                    },
                },
            }]
        }
        with TemporaryDirectory() as temp:
            path = Path(temp) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = CapabilityRegistry.from_json(path)
        self.assertEqual(loaded.get("browser.read", "1.0.0"), entry)


if __name__ == "__main__":
    unittest.main()
