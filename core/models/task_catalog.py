"""A deterministic 1,000-unit task catalog for capability routing lessons.

The catalog is intentionally generated from a stable 10 x 10 x 10 taxonomy.
Each leaf is independently addressable, carries its best currently-admitted
local worker, and can be promoted only through a task-specific acceptance test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .capabilities import DEFAULT_SPECIALIST_CATALOG
from .manager import DEFAULT_MODEL_CATALOG


@dataclass(frozen=True, slots=True)
class TaskUnit:
    task_id: str
    domain: str
    workflow: str
    operation: str
    runtime: str
    model: str | None
    verification: str
    build_path: str


_DOMAINS: tuple[tuple[str, str, str | None, str], ...] = (
    ("text", "ollama", "gemma3:270m", "schema/length/exact-match verifier"),
    ("classification", "ollama", "smollm2:360m", "label-set verifier"),
    ("reasoning", "ollama", "phi4-mini:3.8b-q4_K_M", "structured-answer verifier"),
    ("code", "ollama", "qwen2.5-coder:1.5b-instruct", "lint/test/patch verifier"),
    ("browser", "browser-agent", "qwen3.5:2b-q4_K_M", "origin/action/result verifier"),
    ("vision", "ollama", "qwen3.5:4b-q4_K_M", "grounded-answer verifier"),
    ("retrieval", "embedding-worker", "BAAI/bge-small-en-v1.5", "top-k/relevance verifier"),
    ("speech", "asr-worker", "openai/whisper-tiny", "transcript fixture verifier"),
    ("image", "image-worker", "stabilityai/sd-turbo", "artifact/dimension verifier"),
    ("video", "video-worker", "Wan-AI/Wan2.1-T2V-1.3B", "artifact/duration verifier"),
)
_WORKFLOWS = (
    "intake", "normalize", "extract", "transform", "analyze",
    "plan", "execute", "verify", "recover", "report",
)
_OPERATIONS = (
    "basic", "bounded", "batch", "multilingual", "structured",
    "quality", "latency", "privacy", "failure", "handoff",
)


def default_task_catalog() -> tuple[TaskUnit, ...]:
    units: list[TaskUnit] = []
    for domain, runtime, model, verification in _DOMAINS:
        for workflow in _WORKFLOWS:
            for operation in _OPERATIONS:
                units.append(TaskUnit(
                    task_id=f"{domain}.{workflow}.{operation}",
                    domain=domain,
                    workflow=workflow,
                    operation=operation,
                    runtime=runtime,
                    model=model,
                    verification=verification,
                    build_path=(
                        "use existing verified runtime; add fixture before promotion"
                        if model else "implement deterministic capability and fixture"
                    ),
                ))
    return tuple(units)


class TaskCatalog:
    def __init__(self, units: Iterable[TaskUnit] = ()) -> None:
        self.units = tuple(units) or default_task_catalog()
        known_models = {spec.name for spec in DEFAULT_MODEL_CATALOG} | {
            spec.name for spec in DEFAULT_SPECIALIST_CATALOG
        }
        ids: set[str] = set()
        for unit in self.units:
            if unit.task_id in ids:
                raise ValueError(f"duplicate task unit: {unit.task_id}")
            ids.add(unit.task_id)
            if unit.model is not None and unit.model not in known_models:
                raise ValueError(f"task unit names an unregistered model: {unit.model}")
            if not unit.verification or not unit.build_path:
                raise ValueError("every task unit needs verification and a build path")

    def get(self, task_id: str) -> TaskUnit:
        for unit in self.units:
            if unit.task_id == task_id:
                return unit
        raise KeyError(task_id)

    def by_domain(self, domain: str) -> tuple[TaskUnit, ...]:
        return tuple(unit for unit in self.units if unit.domain == domain)
