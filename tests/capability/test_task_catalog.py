from __future__ import annotations

import unittest

from core.models import TaskCatalog, default_task_catalog


class TaskCatalogTests(unittest.TestCase):
    def test_catalog_has_one_thousand_unique_verified_task_units(self) -> None:
        catalog = TaskCatalog()
        self.assertEqual(len(catalog.units), 1_000)
        self.assertEqual(len({unit.task_id for unit in catalog.units}), 1_000)
        self.assertTrue(all(unit.model for unit in catalog.units))
        self.assertTrue(all(unit.verification for unit in catalog.units))

    def test_each_domain_has_one_hundred_units_and_registered_model(self) -> None:
        catalog = TaskCatalog(default_task_catalog())
        self.assertEqual(len(catalog.by_domain("code")), 100)
        self.assertEqual(catalog.get("code.recover.failure").model, "qwen2.5-coder:1.5b-instruct")
        self.assertEqual(catalog.get("image.execute.quality").runtime, "image-worker")

    def test_unknown_task_is_not_silently_routed(self) -> None:
        with self.assertRaises(KeyError):
            TaskCatalog().get("unknown.task.unit")


if __name__ == "__main__":
    unittest.main()
