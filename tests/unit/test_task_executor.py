from __future__ import annotations

import time
import unittest

from core.contracts import Task, TaskConstraints, TaskStep
from core.planner import TaskExecutor


class TaskExecutorTests(unittest.TestCase):
    def test_dependencies_and_parallel_ready_steps(self):
        started: list[str] = []
        def handler(step, context):
            started.append(step.step_id)
            if step.step_id == "A":
                time.sleep(0.03)
            return step.step_id

        task = Task(
            task_id="t1",
            goal="graph",
            constraints=TaskConstraints(max_parallelism=2),
            steps=(
                TaskStep("A", "cap.a", "A"),
                TaskStep("B", "cap.b", "B"),
                TaskStep("C", "cap.c", "C", ("A", "B")),
            ),
        )
        result = TaskExecutor(handler=handler, max_workers=2).execute(task)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.completed_steps, ("A", "B", "C"))
        self.assertEqual([s.output for s in result.steps], ["A", "B", "C"])
        self.assertEqual(set(started[:2]), {"A", "B"})

    def test_failure_stops_downstream_steps(self):
        called: list[str] = []
        def handler(step, context):
            called.append(step.step_id)
            if step.step_id == "A":
                raise RuntimeError("boom")
            return "ok"

        task = Task(
            task_id="t2",
            goal="fail",
            constraints=TaskConstraints(max_parallelism=2),
            steps=(
                TaskStep("A", "cap.a", "A"),
                TaskStep("B", "cap.b", "B"),
                TaskStep("C", "cap.c", "C", ("A",)),
            ),
        )
        result = TaskExecutor(handler=handler, max_workers=2).execute(task)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.failed_step, "A")
        self.assertNotIn("C", called)

    def test_task_parallelism_is_bounded(self):
        active = 0
        peak = 0

        def handler(step, context):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            time.sleep(0.02)
            active -= 1
            return step.step_id

        task = Task(
            task_id="t3",
            goal="bound",
            constraints=TaskConstraints(max_parallelism=1),
            steps=tuple(
                TaskStep(str(i), "cap", str(i))
                for i in range(4)
            ),
        )
        result = TaskExecutor(handler=handler, max_workers=4).execute(task)
        self.assertTrue(result.succeeded)
        self.assertEqual(peak, 1)

    def test_handler_receives_completed_context(self):
        seen = {}
        def handler(step, context):
            seen[step.step_id] = dict(context)
            return step.step_id + "-out"

        task = Task(
            task_id="t4",
            goal="context",
            steps=(
                TaskStep("A", "cap.a", "A"),
                TaskStep("B", "cap.b", "B", ("A",)),
            ),
        )
        result = TaskExecutor(handler=handler).execute(task)
        self.assertTrue(result.succeeded)
        self.assertEqual(seen["B"]["A"], "A-out")


if __name__ == "__main__":
    unittest.main()
