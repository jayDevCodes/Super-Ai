from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


class ConfigError(ValueError):
    pass


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ConfigError(f"{name} must be > 0")
    return parsed


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Low-footprint defaults for the target 8 GB RAM / 256 GB storage host."""

    host_ram_mb: int = 8192
    storage_gb: int = 256
    scheduler_reserve_ram_mb: int = 1024
    scheduler_reserve_storage_gb: int = 8
    max_concurrent_tasks: int = 2
    cache_soft_limit_gb: int = 8
    cache_hard_limit_gb: int = 24
    default_task_timeout_seconds: int = 900

    def validate(self) -> None:
        if self.host_ram_mb < 1024:
            raise ConfigError("host_ram_mb is unrealistically small")
        if self.storage_gb < 16:
            raise ConfigError("storage_gb is unrealistically small")
        for name in (
            "scheduler_reserve_ram_mb",
            "scheduler_reserve_storage_gb",
            "max_concurrent_tasks",
            "cache_soft_limit_gb",
            "cache_hard_limit_gb",
            "default_task_timeout_seconds",
        ):
            value = getattr(self, name)
            if value <= 0:
                raise ConfigError(f"{name} must be > 0")
        if self.scheduler_reserve_ram_mb >= self.host_ram_mb:
            raise ConfigError("RAM reserve must stay below total host RAM")
        if self.scheduler_reserve_storage_gb >= self.storage_gb:
            raise ConfigError("storage reserve must stay below total storage")
        if self.cache_soft_limit_gb > self.cache_hard_limit_gb:
            raise ConfigError("cache soft limit cannot exceed hard limit")

    @classmethod
    def from_env(cls) -> "EngineConfig":
        cfg = cls(
            host_ram_mb=_positive_int(os.getenv("SUPER_AI_HOST_RAM_MB", "8192"), "SUPER_AI_HOST_RAM_MB"),
            storage_gb=_positive_int(os.getenv("SUPER_AI_STORAGE_GB", "256"), "SUPER_AI_STORAGE_GB"),
            scheduler_reserve_ram_mb=_positive_int(
                os.getenv("SUPER_AI_RAM_RESERVE_MB", "1024"), "SUPER_AI_RAM_RESERVE_MB"
            ),
            scheduler_reserve_storage_gb=_positive_int(
                os.getenv("SUPER_AI_STORAGE_RESERVE_GB", "8"), "SUPER_AI_STORAGE_RESERVE_GB"
            ),
            max_concurrent_tasks=_positive_int(
                os.getenv("SUPER_AI_MAX_CONCURRENT_TASKS", "2"), "SUPER_AI_MAX_CONCURRENT_TASKS"
            ),
            cache_soft_limit_gb=_positive_int(
                os.getenv("SUPER_AI_CACHE_SOFT_GB", "8"), "SUPER_AI_CACHE_SOFT_GB"
            ),
            cache_hard_limit_gb=_positive_int(
                os.getenv("SUPER_AI_CACHE_HARD_GB", "24"), "SUPER_AI_CACHE_HARD_GB"
            ),
            default_task_timeout_seconds=_positive_int(
                os.getenv("SUPER_AI_TASK_TIMEOUT_S", "900"), "SUPER_AI_TASK_TIMEOUT_S"
            ),
        )
        cfg.validate()
        return cfg

    def cache_path(self, root: Path) -> Path:
        root = root.expanduser().resolve()
        return root / "cache"
