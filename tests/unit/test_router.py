from __future__ import annotations

import unittest

from core.contracts import CapabilitySpec, ResourceContract, TaskConstraints
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.router import CapabilityRouter, RouteRequest, RoutingError
from registry.catalog import CapabilityRegistry, RegistryEntry
from registry.manifest import ArtifactSpec, CapabilityManifest


def entry(capability_id, description, permissions=()):
    manifest = CapabilityManifest(
        capability_id=capability_id,
        version="1.0.0",
        description=description,
        artifact=ArtifactSpec(
            repository_url="https://github.com/example/repo",
            pinned_commit="a" * 40,
        ),
    )
    spec = CapabilitySpec(
        capability_id=capability_id,
        version="1.0.0",
        description=description,
        resource=ResourceContract(256, 512),
        permissions=frozenset(permissions),
    )
    return RegistryEntry(manifest=manifest, spec=spec)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry([
            entry("browser.form_fill", "fill web forms", {"browser"}),
            entry("browser.read", "inspect web page", {"browser"}),
            entry("filesystem.delete", "delete files", {"filesystem", "submit"}),
        ])
        self.policy = CapabilityPolicyEngine(
            CapabilityPolicy(
                allowed_permissions=frozenset({"browser", "filesystem", "submit"})
            )
        )
        self.router = CapabilityRouter(self.registry, self.policy)

    def test_exact_id_is_selected_first(self):
        result = self.router.select(
            RouteRequest(goal="fill", capability_id="browser.form_fill")
        )
        self.assertEqual(result.entry.manifest.capability_id, "browser.form_fill")
        self.assertGreaterEqual(result.score, 1000)

    def test_semantic_matching_is_deterministic(self):
        results = self.router.route(RouteRequest(goal="inspect web page"))
        self.assertEqual(results[0].entry.manifest.capability_id, "browser.read")

    def test_required_permissions_filter_candidates(self):
        result = self.router.select(
            RouteRequest(goal="fill form", required_permissions=frozenset({"browser"}))
        )
        self.assertEqual(result.entry.manifest.capability_id, "browser.form_fill")
        self.assertNotEqual(result.entry.manifest.capability_id, "filesystem.delete")

    def test_denied_policy_candidate_is_not_routable(self):
        engine = CapabilityPolicyEngine(
            CapabilityPolicy(allowed_permissions=frozenset({"browser"}))
        )
        router = CapabilityRouter(self.registry, engine)
        with self.assertRaises(RoutingError):
            router.select(RouteRequest(goal="delete files"))

    def test_confirmation_can_be_included_explicitly(self):
        request = RouteRequest(
            goal="delete files",
            required_permissions=frozenset({"filesystem", "submit"}),
            task_constraints=TaskConstraints(
                require_confirmation_for_consequential_actions=True
            ),
        )
        result = self.router.select(request, include_confirmation=True)
        self.assertEqual(result.policy_state.value, "confirm")


if __name__ == "__main__":
    unittest.main()
