from __future__ import annotations

import unittest

from core.resource_feedback import (
    ResourceFeedbackController,
    ResourceObservation,
)


class ResourceFeedbackTests(unittest.TestCase):
    def test_no_history_keeps_conservative_budget(self):
        controller = ResourceFeedbackController(
            execution_ram_capacity_mb=3500,
            cpu_threads=4,
        )
        result = controller.recommend(
            "demo",
            declared_ram_mb=512,
            declared_cpu_threads=1,
            max_parallelism=4,
        )
        self.assertEqual(result.recommended_ram_mb, 512)
        self.assertEqual(result.recommended_parallelism, 1)

    def test_measured_peak_drives_ram_recommendation(self):
        controller = ResourceFeedbackController(
            execution_ram_capacity_mb=3500,
            cpu_threads=4,
            safety_factor=1.25,
        )
        controller.record(
            ResourceObservation(
                capability_id="demo",
                reserved_ram_mb=1024,
                peak_memory_bytes=600 * 1024 * 1024,
                reserved_cpu_threads=1,
                cpu_percent=20.0,
                success=True,
            )
        )
        result = controller.recommend(
            "demo",
            declared_ram_mb=512,
            declared_cpu_threads=1,
            max_parallelism=4,
        )
        self.assertEqual(result.recommended_ram_mb, 750)
        self.assertEqual(result.recommended_parallelism, 4)

    def test_cpu_and_ram_both_bound_parallelism(self):
        controller = ResourceFeedbackController(
            execution_ram_capacity_mb=2000,
            cpu_threads=2,
        )
        controller.record(
            ResourceObservation(
                capability_id="cpu-heavy",
                reserved_ram_mb=512,
                peak_memory_bytes=700 * 1024 * 1024,
                reserved_cpu_threads=2,
                cpu_percent=190.0,
                success=True,
            )
        )
        result = controller.recommend(
            "cpu-heavy",
            declared_ram_mb=512,
            declared_cpu_threads=2,
            max_parallelism=8,
        )
        self.assertEqual(result.recommended_ram_mb, 875)
        self.assertEqual(result.recommended_parallelism, 1)

    def test_history_is_bounded(self):
        controller = ResourceFeedbackController(
            execution_ram_capacity_mb=3500,
            cpu_threads=4,
            max_observations_per_capability=2,
        )
        for i in range(4):
            controller.record(
                ResourceObservation(
                    capability_id="demo",
                    reserved_ram_mb=256,
                    peak_memory_bytes=(256 + i) * 1024 * 1024,
                    reserved_cpu_threads=1,
                    cpu_percent=1,
                    success=True,
                )
            )
        self.assertEqual(len(controller.observations("demo")), 2)


if __name__ == "__main__":
    unittest.main()
