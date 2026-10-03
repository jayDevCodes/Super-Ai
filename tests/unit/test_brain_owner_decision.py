from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.brain import Brain
from core.contracts import CapabilitySpec, ResourceContract, Task, TaskStep
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.router import CapabilityRouter, RoutingError
from core.security import OwnerAuthorization
from registry.catalog import CapabilityRegistry, RegistryEntry
from registry.manifest import ArtifactSpec, CapabilityManifest


def browser_entry() -> RegistryEntry:
    manifest = CapabilityManifest(
        capability_id="browser.agent",
        version="1.0.0",
        description="controlled browser agent",
        artifact=ArtifactSpec(
            repository_url="https://github.com/example/browser",
            pinned_commit="a" * 40,
        ),
    )
    spec = CapabilitySpec(
        capability_id="browser.agent",
        version="1.0.0",
        description="controlled browser agent",
        resource=ResourceContract(256, 512, 512, 1, 1),
        permissions=frozenset({"browser", "network"}),
    )
    return RegistryEntry(manifest=manifest, spec=spec)


class Runner:
    def __init__(self) -> None:
        self.contexts = []

    def run(self, route, step, context):
        self.contexts.append(dict(context))
        return "completed"


class BrainOwnerDecisionTests(unittest.TestCase):
    def test_owner_code_is_needed_only_for_a_policy_conflict(self) -> None:
        with TemporaryDirectory() as directory:
            auth = OwnerAuthorization(Path(directory) / "owner_auth.json")
            secret = "a-strong-owner-code-2026!"
            auth.configure(secret)

            registry = CapabilityRegistry([browser_entry()])
            policy = CapabilityPolicyEngine(
                CapabilityPolicy(allowed_permissions=frozenset({"browser"}))
            )
            runner = Runner()
            brain = Brain(
                router=CapabilityRouter(registry, policy),
                runner=runner,
                owner_authorization=auth,
            )
            task = Task(
                task_id="owner-1",
                goal="use the browser despite the current network policy",
                steps=(
                    TaskStep(
                        "browse",
                        "browser.agent",
                        "open the approved page",
                    ),
                ),
            )

            with self.assertRaises(RoutingError):
                brain.execute(task)

            result = brain.execute(task, owner_override_code=secret)
            self.assertTrue(result.succeeded)
            self.assertEqual(len(runner.contexts), 1)
            self.assertNotIn("owner_override_code", runner.contexts[0])
            self.assertNotIn(secret, str(runner.contexts[0]))

    def test_owner_code_can_resolve_confirmation_state(self) -> None:
        with TemporaryDirectory() as directory:
            auth = OwnerAuthorization(Path(directory) / "owner_auth.json")
            secret = "a-strong-owner-code-2026!"
            auth.configure(secret)

            registry = CapabilityRegistry([browser_entry()])
            policy = CapabilityPolicyEngine(
                CapabilityPolicy(
                    allowed_permissions=frozenset({"browser", "network"})
                )
            )
            runner = Runner()
            brain = Brain(
                router=CapabilityRouter(registry, policy),
                runner=runner,
                owner_authorization=auth,
            )
            task = Task(
                task_id="confirm-1",
                goal="open the approved page",
                steps=(
                    TaskStep("browse", "browser.agent", "open the approved page"),
                ),
            )

            self.assertTrue(brain.execute(task).succeeded)


if __name__ == "__main__":
    unittest.main()
