import unittest

from core.contracts import ResourceContract, TaskConstraints
from core.contracts.scheduler import (
    ResourceBudget,
    ResourceLimitError,
    ResourceScheduler,
    ResourceSnapshot,
)


class ResourceSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = ResourceScheduler(
            ResourceSnapshot(
                total_ram_mb=8192,
                available_ram_mb=7000,
                free_disk_mb=10000,
                cpu_threads=8,
            ),
            ResourceBudget(
                system_reserved_ram_mb=2000,
                control_plane_reserved_ram_mb=700,
                safety_reserve_ram_mb=700,
                max_parallel_workers=4,
            ),
        )

    def test_uses_peak_ram_for_admission(self):
        contract = ResourceContract(
            ram_soft_mb=300,
            ram_hard_mb=4200,
            cpu_threads=2,
        )
        self.assertTrue(self.scheduler.can_admit(contract))

    def test_respects_eight_gb_execution_budget_and_safety_reserve(self):
        first = self.scheduler.reserve(
            "worker.a",
            ResourceContract(
                ram_soft_mb=1000,
                ram_hard_mb=3500,
                cpu_threads=2,
            ),
        )
        self.assertEqual(first.reserved_ram_mb, 3500)
        self.assertFalse(
            self.scheduler.can_admit(
                ResourceContract(
                    ram_soft_mb=1000,
                    ram_hard_mb=2000,
                    cpu_threads=2,
                )
            )
        )

    def test_release_returns_capacity(self):
        allocation = self.scheduler.reserve(
            "worker.a",
            ResourceContract(
                ram_soft_mb=500,
                ram_hard_mb=1500,
                disk_mb=100,
                cpu_threads=1,
            ),
        )
        self.scheduler.release(allocation)
        self.assertEqual(self.scheduler.reserved_ram_mb, 0)
        self.assertTrue(
            self.scheduler.can_admit(
                ResourceContract(
                    ram_soft_mb=500,
                    ram_hard_mb=3000,
                    cpu_threads=2,
                )
            )
        )

    def test_task_limits_override_machine_capacity(self):
        task_limits = TaskConstraints(
            max_ram_mb=800,
            max_disk_mb=500,
            max_parallelism=2,
        )
        contract = ResourceContract(
            ram_soft_mb=200,
            ram_hard_mb=900,
            disk_mb=100,
            cpu_threads=1,
        )
        self.assertFalse(self.scheduler.can_admit(contract, task_limits))

    def test_parallel_worker_limit(self):
        contract = ResourceContract(
            ram_soft_mb=100,
            ram_hard_mb=300,
            cpu_threads=1,
            max_concurrency=4,
        )
        allocations = [
            self.scheduler.reserve(f"worker.{i}", contract) for i in range(4)
        ]
        self.assertFalse(self.scheduler.can_admit(contract))
        for allocation in allocations:
            self.scheduler.release(allocation)

    def test_per_capability_concurrency_limit(self):
        contract = ResourceContract(
            ram_soft_mb=100,
            ram_hard_mb=300,
            cpu_threads=1,
            max_concurrency=1,
        )
        self.scheduler.reserve("same.skill", contract)
        with self.assertRaises(ResourceLimitError):
            self.scheduler.reserve("same.skill", contract)

    def test_disk_and_cpu_are_admission_constraints(self):
        disk_contract = ResourceContract(
            ram_soft_mb=100,
            ram_hard_mb=200,
            disk_mb=11000,
            cpu_threads=1,
        )
        self.assertFalse(self.scheduler.can_admit(disk_contract))

        cpu_contract = ResourceContract(
            ram_soft_mb=100,
            ram_hard_mb=200,
            disk_mb=0,
            cpu_threads=9,
        )
        self.assertFalse(self.scheduler.can_admit(cpu_contract))


if __name__ == "__main__":
    unittest.main()
