from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.brain import Brain, BrainError
from core.contracts import (
    CapabilitySpec,
    ResourceContract,
    Task,
    TaskConstraints,
    TaskStep,
)
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.router import CapabilityRouter
from registry.catalog import CapabilityRegistry, RegistryEntry
from registry.manifest import ArtifactSpec, CapabilityManifest
from core.audit import HashChainAuditStore


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


class Runner:
    def __init__(self):
        self.calls = []

    def run(self, route, step, context):
        self.calls.append((step.step_id, route.entry.manifest.capability_id, dict(context)))
        return step.step_id + "-done"


class BrainTests(unittest.TestCase):
    def setUp(self):
        registry = CapabilityRegistry([
            entry("browser.read", "inspect web page", {"browser"}),
            entry("browser.fill", "fill web form", {"browser"}),
        ])
        policy = CapabilityPolicyEngine(
            CapabilityPolicy(allowed_permissions=frozenset({"browser"}))
        )
        self.runner = Runner()
        self.brain = Brain(
            router=CapabilityRouter(registry, policy),
            runner=self.runner,
            max_workers=2,
        )

    def test_plan_routes_each_task_step(self):
        task = Task(
            task_id="T1",
            goal="web",
            steps=(
                TaskStep("a", "browser.read", "inspect web page"),
                TaskStep("b", "browser.fill", "fill web form", ("a",)),
            ),
        )
        plan = self.brain.plan(task)
        self.assertEqual(
            [x.route.entry.manifest.capability_id for x in plan.steps],
            ["browser.read", "browser.fill"],
        )
        self.assertFalse(plan.requires_confirmation)
        self.assertRegex(plan.trace_context.trace_id, r"^[0-9a-f]{32}$")

    def test_execute_delegates_through_task_executor(self):
        task = Task(
            task_id="T2",
            goal="web",
            steps=(
                TaskStep("a", "browser.read", "inspect web page"),
                TaskStep("b", "browser.fill", "fill web form", ("a",)),
            ),
        )
        result = self.brain.execute(task)
        self.assertTrue(result.succeeded)
        self.assertEqual([x[0] for x in self.runner.calls], ["a", "b"])
        self.assertEqual(self.runner.calls[1][2]["a"], "a-done")

    def test_confirmation_is_required_for_consequential_capability(self):
        registry = CapabilityRegistry([
            entry("browser.submit", "submit web form", {"browser", "submit"}),
        ])
        policy = CapabilityPolicyEngine(
            CapabilityPolicy(
                allowed_permissions=frozenset({"browser", "submit"})
            )
        )
        runner = Runner()
        brain = Brain(
            router=CapabilityRouter(registry, policy),
            runner=runner,
        )
        task = Task(
            task_id="T3",
            goal="submit",
            steps=(TaskStep("s", "browser.submit", "submit web form"),),
        )
        with self.assertRaises(BrainError):
            brain.execute(task)
        result = brain.execute(task, confirmed=True)
        self.assertTrue(result.succeeded)

    def test_audit_events_are_recorded(self):
        with TemporaryDirectory() as temp:
            audit = HashChainAuditStore(Path(temp) / "audit.jsonl")
            brain = Brain(
                router=self.brain._router,
                runner=self.runner,
                audit_store=audit,
            )
            task = Task(
                task_id="T4",
                goal="read",
                steps=(TaskStep("s", "browser.read", "inspect web page"),),
            )
            brain.execute(task)
            names = [event.event_name for event in audit.read_all()]
            self.assertIn("brain.plan_created", names)
            self.assertIn("brain.execution_finished", names)
            self.assertTrue(audit.verify())
            self.assertTrue(
                all(
                    "trace_id" in event.attributes
                    for event in audit.read_all()
                )
            )


if __name__ == "__main__":
    unittest.main()
