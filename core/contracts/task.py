from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .resources import TaskConstraints


@dataclass(frozen=True, slots=True)
class TaskStep:
    """One executable node in the task DAG."""

    step_id: str
    capability_id: str
    description: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        for value, label in ((self.step_id, "step_id"), (self.capability_id, "capability_id")):
            if not value or value.strip() != value:
                raise ValueError(f"{label} must be a non-empty trimmed string")
        if not self.description.strip():
            raise ValueError("description must be non-empty")
        if self.step_id in self.dependencies:
            raise ValueError(f"step {self.step_id!r} cannot depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError(f"step {self.step_id!r} contains duplicate dependencies")


@dataclass(frozen=True, slots=True)
class Task:
    """A user goal represented as a validated directed acyclic graph."""

    task_id: str
    goal: str
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    steps: tuple[TaskStep, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.task_id or self.task_id.strip() != self.task_id:
            raise ValueError("task_id must be a non-empty trimmed string")
        if not self.goal.strip():
            raise ValueError("goal must be non-empty")
        self.constraints.validate()

        step_map: dict[str, TaskStep] = {}
        for step in self.steps:
            step.validate()
            if step.step_id in step_map:
                raise ValueError(f"duplicate step_id: {step.step_id}")
            step_map[step.step_id] = step

        for step in self.steps:
            missing = set(step.dependencies) - step_map.keys()
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"step {step.step_id!r} has missing dependencies: {names}")

        self._assert_acyclic(step_map)

    @staticmethod
    def _assert_acyclic(step_map: dict[str, TaskStep]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("task dependency graph contains a cycle")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in step_map[step_id].dependencies:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_map:
            visit(step_id)

    def ready_steps(self, completed: Iterable[str]) -> tuple[TaskStep, ...]:
        """Return steps whose dependencies are all completed."""

        completed_set = set(completed)
        return tuple(
            step
            for step in self.steps
            if step.step_id not in completed_set and set(step.dependencies) <= completed_set
        )
