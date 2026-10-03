"""Catalog and resource gate for optional specialist model workers.

This is deliberately metadata-only: registering a candidate never downloads it
or gives it permissions. A runtime adapter must separately verify provenance,
resources, and its output contract before execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class SpecialistModelSpec:
    name: str
    capability: str
    task_tags: frozenset[str]
    disk_mb: int
    estimated_ram_mb: int
    estimated_vram_mb: int | None
    requires_accelerator: bool
    storage_strategy: str
    license_name: str
    source_url: str

    def validate(self) -> None:
        if not self.name or self.name.strip() != self.name:
            raise ValueError("specialist model name must be a non-empty trimmed string")
        if not self.capability or not self.task_tags:
            raise ValueError("specialist model must declare capability and task tags")
        if self.disk_mb <= 0 or self.estimated_ram_mb <= 0:
            raise ValueError("specialist model resource estimates must be > 0")
        if self.estimated_vram_mb is not None and self.estimated_vram_mb <= 0:
            raise ValueError("estimated_vram_mb must be > 0 when supplied")
        if self.storage_strategy not in {"single", "quantized", "sharded", "offloaded"}:
            raise ValueError("unsupported specialist storage strategy")
        if not self.license_name or not self.source_url.startswith("https://"):
            raise ValueError("specialist model requires license and HTTPS source")


@dataclass(frozen=True, slots=True)
class SpecialistSelection:
    spec: SpecialistModelSpec
    reason: str


DEFAULT_SPECIALIST_CATALOG: tuple[SpecialistModelSpec, ...] = (
    SpecialistModelSpec(
        name="BAAI/bge-small-en-v1.5", capability="embedding",
        task_tags=frozenset({"retrieve", "semantic-search", "memory"}),
        disk_mb=200, estimated_ram_mb=500, estimated_vram_mb=None,
        requires_accelerator=False, storage_strategy="single", license_name="mit",
        source_url="https://huggingface.co/BAAI/bge-small-en-v1.5",
    ),
    SpecialistModelSpec(
        name="openai/whisper-tiny", capability="speech-to-text",
        task_tags=frozenset({"transcribe", "speech", "audio"}),
        disk_mb=150, estimated_ram_mb=600, estimated_vram_mb=None,
        requires_accelerator=False, storage_strategy="single", license_name="mit",
        source_url="https://github.com/openai/whisper/blob/main/model-card.md",
    ),
    SpecialistModelSpec(
        name="PaddleOCR/PP-OCRv6-mobile", capability="ocr",
        task_tags=frozenset({"ocr", "document", "extract"}),
        disk_mb=200, estimated_ram_mb=800, estimated_vram_mb=None,
        requires_accelerator=False, storage_strategy="single", license_name="apache-2.0",
        source_url="https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md",
    ),
    SpecialistModelSpec(
        name="stabilityai/sd-turbo", capability="image-generation",
        task_tags=frozenset({"image", "generate", "illustrate"}),
        disk_mb=13_000, estimated_ram_mb=16_000, estimated_vram_mb=8_000,
        requires_accelerator=True, storage_strategy="offloaded", license_name="stability-ai-community",
        source_url="https://huggingface.co/stabilityai/sd-turbo",
    ),
    SpecialistModelSpec(
        name="Wan-AI/Wan2.1-T2V-1.3B", capability="video-generation",
        task_tags=frozenset({"video", "generate", "animate"}),
        disk_mb=8_000, estimated_ram_mb=16_000, estimated_vram_mb=8_000,
        requires_accelerator=True, storage_strategy="sharded", license_name="apache-2.0",
        source_url="https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B",
    ),
)


class SpecialistModelRegistry:
    """Select a smallest admissible specialist without installing it."""

    def __init__(self, catalog: Iterable[SpecialistModelSpec] = DEFAULT_SPECIALIST_CATALOG) -> None:
        self.catalog = tuple(catalog)
        if not self.catalog:
            raise ValueError("specialist catalog must not be empty")
        for spec in self.catalog:
            spec.validate()

    def select(
        self, capability: str, *, max_ram_mb: int, max_disk_mb: int,
        accelerator_available: bool = False, max_vram_mb: int | None = None,
    ) -> SpecialistSelection:
        if not capability or max_ram_mb <= 0 or max_disk_mb <= 0:
            raise ValueError("capability and positive RAM/disk budgets are required")
        candidates = [
            spec for spec in self.catalog
            if spec.capability == capability
            and spec.estimated_ram_mb <= max_ram_mb
            and spec.disk_mb <= max_disk_mb
            and (not spec.requires_accelerator or accelerator_available)
            and (spec.estimated_vram_mb is None or max_vram_mb is None or spec.estimated_vram_mb <= max_vram_mb)
        ]
        if not candidates:
            raise LookupError("no specialist model fits this capability/resource envelope")
        chosen = min(candidates, key=lambda spec: (spec.estimated_vram_mb or 0, spec.estimated_ram_mb, spec.disk_mb, spec.name))
        return SpecialistSelection(
            spec=chosen,
            reason=(f"capability={capability}, accelerator={accelerator_available}, "
                    f"ram_budget={max_ram_mb}MB, disk_budget={max_disk_mb}MB"),
        )
