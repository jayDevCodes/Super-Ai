from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceContract:
    """Declared resource envelope for one capability."""

    ram_soft_mb: int
    ram_hard_mb: int
    disk_mb: int = 0
    cpu_threads: int = 1
    max_concurrency: int = 1

    def validate(self) -> None:
        if self.ram_soft_mb <= 0:
            raise ValueError("ram_soft_mb must be > 0")
        if self.ram_hard_mb < self.ram_soft_mb:
            raise ValueError("ram_hard_mb must be >= ram_soft_mb")
        if self.disk_mb < 0:
            raise ValueError("disk_mb must be >= 0")
        if self.cpu_threads <= 0:
            raise ValueError("cpu_threads must be > 0")
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be > 0")


@dataclass(frozen=True, slots=True)
class TaskConstraints:
    """Resource and execution limits attached to a task."""

    max_ram_mb: int = 4096
    max_disk_mb: int = 2048
    max_parallelism: int = 1
    allow_network: bool = False
    require_confirmation_for_consequential_actions: bool = True

    def validate(self) -> None:
        if self.max_ram_mb <= 0:
            raise ValueError("max_ram_mb must be > 0")
        if self.max_disk_mb < 0:
            raise ValueError("max_disk_mb must be >= 0")
        if self.max_parallelism <= 0:
            raise ValueError("max_parallelism must be > 0")
