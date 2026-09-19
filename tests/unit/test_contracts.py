import unittest

from core.contracts import CapabilitySpec, ResourceContract, Task, TaskConstraints, TaskStep


class ContractValidationTests(unittest.TestCase):
    def test_resource_contract_rejects_hard_limit_below_soft_limit(self):
        contract = ResourceContract(ram_soft_mb=512, ram_hard_mb=256)
        with self.assertRaisesRegex(ValueError, "ram_hard_mb"):
            contract.validate()

    def test_capability_spec_accepts_valid_resource_contract(self):
        spec = CapabilitySpec(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill known browser form fields.",
            resource=ResourceContract(
                ram_soft_mb=256,
                ram_hard_mb=1024,
                disk_mb=128,
                cpu_threads=2,
            ),
            permissions=frozenset({"browser"}),
        )
        spec.validate()

    def test_task_rejects_missing_dependency(self):
        task = Task(
            task_id="T-001",
            goal="Fill a form",
            steps=(
                TaskStep("fill", "browser.form_fill", "Fill fields", ("inspect",)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "missing dependencies"):
            task.validate()

    def test_task_rejects_cycles(self):
        task = Task(
            task_id="T-002",
            goal="Complete a workflow",
            steps=(
                TaskStep("a", "skill.a", "A", ("b",)),
                TaskStep("b", "skill.b", "B", ("a",)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            task.validate()

    def test_ready_steps_only_returns_nodes_with_completed_dependencies(self):
        task = Task(
            task_id="T-003",
            goal="Fill a form",
            constraints=TaskConstraints(max_ram_mb=6000, max_parallelism=2),
            steps=(
                TaskStep("inspect", "browser.inspect", "Inspect page"),
                TaskStep("map", "browser.map_fields", "Map fields", ("inspect",)),
                TaskStep("fill", "browser.form_fill", "Fill fields", ("map",)),
            ),
        )
        task.validate()

        self.assertEqual([s.step_id for s in task.ready_steps([])], ["inspect"])
        self.assertEqual([s.step_id for s in task.ready_steps(["inspect"])], ["map"])
        self.assertEqual([s.step_id for s in task.ready_steps(["inspect", "map"])], ["fill"])


if __name__ == "__main__":
    unittest.main()
