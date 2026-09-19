from __future__ import annotations

import unittest

from core.contracts import CapabilitySpec, ResourceContract, TaskConstraints
from core.policy import CapabilityPolicy, CapabilityPolicyEngine, PolicyDecisionState


def spec(*permissions, ram=256, cpu=1):
    return CapabilitySpec(
        capability_id="demo",
        version="1.0.0",
        description="demo",
        resource=ResourceContract(ram, ram, cpu_threads=cpu),
        permissions=frozenset(permissions),
    )


class PolicyEngineTests(unittest.TestCase):
    def test_unknown_permissions_are_denied_by_default(self):
        decision = CapabilityPolicyEngine().evaluate(spec("browser"))
        self.assertEqual(decision.state, PolicyDecisionState.DENY)

    def test_allowlisted_capability_can_run_without_network(self):
        engine = CapabilityPolicyEngine(
            CapabilityPolicy(allowed_permissions=frozenset({"browser"}))
        )
        decision = engine.evaluate(spec("browser"))
        self.assertEqual(decision.state, PolicyDecisionState.ALLOW)
        self.assertEqual(decision.network, "disabled")

    def test_network_requires_both_task_and_capability_permission(self):
        engine = CapabilityPolicyEngine(
            CapabilityPolicy(allowed_permissions=frozenset({"network"}))
        )
        self.assertEqual(
            engine.evaluate(spec("network"), TaskConstraints(allow_network=True)).state,
            PolicyDecisionState.ALLOW,
        )
        self.assertEqual(
            engine.evaluate(spec("network"), TaskConstraints(allow_network=False)).state,
            PolicyDecisionState.DENY,
        )

    def test_resource_ceiling_is_enforced(self):
        engine = CapabilityPolicyEngine(
            CapabilityPolicy(
                allowed_permissions=frozenset(),
                max_ram_mb=512,
                max_cpu_threads=1,
            )
        )
        decision = engine.evaluate(spec(ram=1024))
        self.assertEqual(decision.state, PolicyDecisionState.DENY)

    def test_consequential_action_requests_confirmation(self):
        engine = CapabilityPolicyEngine(
            CapabilityPolicy(allowed_permissions=frozenset({"submit"}))
        )
        decision = engine.evaluate(
            spec("submit"),
            TaskConstraints(require_confirmation_for_consequential_actions=True),
        )
        self.assertEqual(decision.state, PolicyDecisionState.CONFIRM)


if __name__ == "__main__":
    unittest.main()
