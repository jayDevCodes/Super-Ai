from __future__ import annotations

from contextlib import contextmanager
import unittest

from core.models import ModelManagerError, TaskModelManager


class FakeModelManager(TaskModelManager):
    def __init__(self) -> None:
        super().__init__()
        self.installed: set[str] = set()
        self.events: list[tuple[str, str]] = []

    def is_installed(self, model: str) -> bool:
        self.events.append(("is_installed", model))
        return model in self.installed

    def ensure_installed(self, selection) -> None:
        self.events.append(("ensure_installed", selection.model))
        self.installed.add(selection.model)

    def unload(self, model: str) -> None:
        self.events.append(("unload", model))

    def remove(self, model: str) -> None:
        self.events.append(("remove", model))
        self.installed.discard(model)


class ModelManagerTests(unittest.TestCase):
    def test_micro_task_prefers_smallest_catalog_model(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Extract a short label from this text",
            max_ram_mb=1000,
            max_disk_mb=500,
        )
        self.assertEqual(selection.model, "gemma3:270m")
        self.assertEqual(selection.spec.license_name, "gemma")

    def test_tight_browser_budget_uses_qwen_lite_fallback(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Browse a page and extract the title",
            max_ram_mb=1600,
            max_disk_mb=1200,
        )
        self.assertEqual(selection.model, "qwen3.5:0.8b")

    def test_classification_task_uses_compact_apache_model(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Classify this short message into one label",
            max_ram_mb=1200,
            max_disk_mb=1000,
        )
        self.assertEqual(selection.model, "smollm2:360m")
        self.assertEqual(selection.spec.license_name, "apache-2.0")

    def test_mid_budget_reasoning_can_use_phi_mini(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Reason through this coding problem and explain the answer",
            max_ram_mb=3500,
            max_disk_mb=3000,
        )
        self.assertEqual(selection.model, "phi4-mini:3.8b-q4_K_M")

    def test_browser_budget_prefers_smallest_viable_model(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Open the Google webpage and inspect the current page",
            max_ram_mb=3000,
            max_disk_mb=2200,
        )
        self.assertEqual(selection.model, "qwen3.5:2b-q4_K_M")

    def test_complex_browser_task_can_select_four_billion_model(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Research and analyze a complex multi-step browser workflow with visual screenshots",
            max_ram_mb=4096,
            max_disk_mb=4096,
        )
        self.assertEqual(selection.model, "qwen3.5:4b-q4_K_M")
        self.assertTrue(selection.spec.supports_vision)

    def test_budget_can_force_lightweight_model(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Browse a page and extract the title",
            max_ram_mb=1600,
            max_disk_mb=1200,
        )
        self.assertEqual(selection.model, "qwen3.5:0.8b")

    def test_browser_capability_footprint_is_reserved_from_model_budget(self) -> None:
        manager = TaskModelManager()
        selection = manager.select(
            "Research a complex browser task",
            max_ram_mb=4096,
            max_disk_mb=4096,
            reserved_ram_mb=1024,
            reserved_disk_mb=512,
        )
        self.assertEqual(selection.model, "qwen3.5:2b-q4_K_M")

    def test_no_model_fits_budget(self) -> None:
        manager = TaskModelManager()
        with self.assertRaises(ModelManagerError):
            manager.select(
                "Open a complex browser workflow",
                max_ram_mb=500,
                max_disk_mb=200,
            )

    def test_ephemeral_model_is_unloaded_and_removed_when_downloaded(self) -> None:
        manager = FakeModelManager()
        selection = manager.selection_for_model("qwen3.5:2b-q4_K_M")

        with manager.use(selection):
            self.assertIn(selection.model, manager.installed)

        self.assertEqual(
            manager.events,
            [
                ("is_installed", selection.model),
                ("ensure_installed", selection.model),
                ("unload", selection.model),
                ("remove", selection.model),
            ],
        )
        self.assertNotIn(selection.model, manager.installed)

    def test_preexisting_model_is_unloaded_but_not_deleted(self) -> None:
        manager = FakeModelManager()
        selection = manager.selection_for_model("qwen3.5:2b-q4_K_M")
        manager.installed.add(selection.model)

        with manager.use(selection):
            pass

        self.assertEqual(
            manager.events,
            [
                ("is_installed", selection.model),
                ("unload", selection.model),
            ],
        )
        self.assertIn(selection.model, manager.installed)

    def test_explicit_unknown_model_is_rejected(self) -> None:
        manager = TaskModelManager()
        with self.assertRaises(ModelManagerError):
            manager.selection_for_model("some-unknown-model")


if __name__ == "__main__":
    unittest.main()
