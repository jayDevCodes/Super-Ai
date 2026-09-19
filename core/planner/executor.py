from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Callable, Mapping

from core.contracts import Task, TaskStep


class TaskExecutionError(RuntimeError):
    """Raised when a task graph cannot be executed safely."""


@dataclass(frozen=True, slots=True)
class StepExecution:
    step_id: str
    success: bool
    output: object | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    task_id: str
    completed_steps: tuple[str, ...]
    failed_step: str | None
    steps: tuple[StepExecution, ...]
    succeeded: bool


StepHandler = Callable[[TaskStep, Mapping[str, object]], object]


class TaskExecutor:
    """Execute validated task DAGs with bounded dependency-aware parallelism."""

    def __init__(self, *, handler: StepHandler, max_workers: int = 4) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be > 0")
        self._handler = handler
        self._max_workers = max_workers

    def execute(
        self,
        task: Task,
        *,
        initial_context: Mapping[str, object] | None = None,
    ) -> TaskExecutionResult:
        task.validate()
        context: dict[str, object] = dict(initial_context or {})
        step_map = {step.step_id: step for step in task.steps}

        graph = {
            step.step_id: set(step.dependencies)
            for step in task.steps
        }
        try:
            sorter = TopologicalSorter(graph)
            sorter.prepare()
        except CycleError as exc:
            raise TaskExecutionError("task graph contains a cycle") from exc

        max_parallel = min(task.constraints.max_parallelism, self._max_workers)
        completed: list[str] = []
        results: dict[str, StepExecution] = {}
        futures: dict[Future[StepExecution], str] = {}

        with ThreadPoolExecutor(
            max_workers=max_parallel,
            thread_name_prefix="super-ai-task",
        ) as executor:
            while sorter.is_active():
                ready = sorter.get_ready()
                if ready:
                    for step_id in sorted(ready):
                        step = step_map[step_id]
                        futures[
                            executor.submit(self._run_step, step, context)
                        ] = step_id

                if not futures:
                    raise TaskExecutionError(
                        "task graph made no progress while work remained"
                    )

                done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: futures[item]):
                    step_id = futures.pop(future)
                    result = future.result()
                    results[step_id] = result

                    if not result.success:
                        for pending in futures:
                            pending.cancel()
                        failed = result
                        ordered = tuple(
                            results[key] for key in sorted(results)
                        )
                        return TaskExecutionResult(
                            task_id=task.task_id,
                            completed_steps=tuple(sorted(completed)),
                            failed_step=failed.step_id,
                            steps=ordered,
                            succeeded=False,
                        )

                    completed.append(step_id)
                    if result.output is not None:
                        context[step_id] = result.output
                    sorter.done(step_id)

        ordered = tuple(results[key] for key in sorted(results))
        return TaskExecutionResult(
            task_id=task.task_id,
            completed_steps=tuple(sorted(completed)),
            failed_step=None,
            steps=ordered,
            succeeded=True,
        )

    def _run_step(
        self,
        step: TaskStep,
        context: Mapping[str, object],
    ) -> StepExecution:
        try:
            output = self._handler(step, dict(context))
            return StepExecution(step_id=step.step_id, success=True, output=output)
        except Exception as exc:
            return StepExecution(
                step_id=step.step_id,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
