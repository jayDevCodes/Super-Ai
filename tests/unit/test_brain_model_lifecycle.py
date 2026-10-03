from __future__ import annotations

from contextlib import contextmanager
import unittest

from core.brain import Brain
from core.contracts import CapabilitySpec, ResourceContract, Task, TaskConstraints, TaskStep
from core.policy import CapabilityPolicy, CapabilityPolicyEngine
from core.router import CapabilityRouter
from registry.catalog import CapabilityRegistry, RegistryEntry
from registry.manifest import ArtifactSpec, CapabilityManifest
from core.models import ModelSelection, ModelSpec


def make_entry() -> RegistryEntry:
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


class RecordingRunner:
    requires_model = True

    def __init__(self) -> None:
        self.contexts = []

    def run(self, route, step, context):
        self.contexts.append(dict(context))
        return "ok"


class RecordingModelManager:
    def __init__(self) -> None:
        self.calls = []

    @contextmanager
    def use_for_task(self, goal, *, max_ram_mb=None, max_disk_mb=None, **kwargs):
        self.calls.append((goal, max_ram_mb, max_disk_mb))
        spec = ModelSpec(
            name="qwen3.5:2b-q4_K_M",
            family="qwen3.5",
            disk_mb=1900,
            estimated_ram_mb=2600,
            supports_vision=True,
            task_tags=frozenset({"browser"}),
        )
        selection = ModelSelection(spec=spec, reason="browser budget selection")
        try:
            yield selection
        finally:
            self.calls.append(("released", selection.model))


class BrainModelLifecycleTests(unittest.TestCase):
    def test_brain_selects_task_model_and_releases_it_after_runner(self) -> None:
        registry = CapabilityRegistry([make_entry()])
        policy = CapabilityPolicyEngine(
            CapabilityPolicy(
                allowed_permissions=frozenset({"browser", "network"})
            )
        )
        runner = RecordingRunner()
        manager = RecordingModelManager()
        brain = Brain(
            router=CapabilityRouter(registry, policy),
            runner=runner,
            model_manager=manager,
        )

        task = Task(
            task_id="browser-1",
            goal="inspect browser page",
            constraints=TaskConstraints(
                max_ram_mb=3000,
                max_disk_mb=2200,
                max_parallelism=1,
                allow_network=True,
            ),
            steps=(
                TaskStep(
                    "browse",
                    "browser.agent",
                    "open the Google webpage and inspect it",
                ),
            ),
        )

        result = brain.execute(task)
        self.assertTrue(result.succeeded)
        self.assertEqual(
            manager.calls,
            [
                ("open the Google webpage and inspect it", 3000, 2200),
                ("released", "qwen3.5:2b-q4_K_M"),
            ],
        )
        self.assertEqual(
            runner.contexts[0]["__model_name"],
            "qwen3.5:2b-q4_K_M",
        )
        self.assertEqual(
            runner.contexts[0]["__model_reason"],
            "browser budget selection",
        )


if __name__ == "__main__":
    unittest.main()
