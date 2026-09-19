from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol
from uuid import uuid4

from core.contracts import (
    Allocation,
    Capability,
    CapabilitySpec,
    ResourceScheduler,
    TaskConstraints,
)
from registry.manifest import CapabilityManifest


class LoaderState(str, Enum):
    """Lifecycle state of a dynamically loaded capability."""

    STAGED = "staged"
    ACTIVE = "active"
    UNLOADED = "unloaded"


class LoadError(RuntimeError):
    """Raised when a capability cannot be loaded safely."""


class UntrustedSourceError(LoadError):
    """Raised when the source does not satisfy the trust boundary."""


class CapabilityFactory(Protocol):
    def __call__(self, manifest: CapabilityManifest, workdir: Path) -> Capability:
        ...


@dataclass(slots=True)
class LoadedCapability:
    """Handle for one ephemeral capability instance."""

    load_id: str
    manifest: CapabilityManifest
    allocation: Allocation
    workdir: Path
    capability: Capability
    _tempdir: TemporaryDirectory[str]
    state: LoaderState = LoaderState.ACTIVE


class CapabilityLoader:
    """Resource-gated, ephemeral capability lifecycle manager.

    The loader deliberately does not clone or execute arbitrary GitHub code itself.
    A trusted staging/factory implementation is injected at the boundary so that
    source retrieval, sandboxing, and artifact verification can be hardened
    independently of lifecycle/resource logic.
    """

    def __init__(
        self,
        scheduler: ResourceScheduler,
        staging_factory: CapabilityFactory,
    ) -> None:
        self._scheduler = scheduler
        self._staging_factory = staging_factory
        self._active: dict[str, LoadedCapability] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    def load(
        self,
        manifest: CapabilityManifest,
        capability_spec: CapabilitySpec,
        task_constraints: TaskConstraints | None = None,
    ) -> LoadedCapability:
        manifest.validate()
        capability_spec.validate()

        if manifest.capability_id != capability_spec.capability_id:
            raise LoadError(
                "manifest and capability spec capability_id values do not match"
            )
        if manifest.version != capability_spec.version:
            raise LoadError("manifest and capability spec versions do not match")

        allocation = self._scheduler.reserve(
            capability_spec.capability_id,
            capability_spec.resource,
            task_constraints,
        )

        tempdir = TemporaryDirectory(
            prefix=f"super-ai-{manifest.capability_id.replace('.', '-')}-"
        )
        workdir = Path(tempdir.name)

        try:
            capability = self._staging_factory(manifest, workdir)
            if capability.spec.capability_id != capability_spec.capability_id:
                raise LoadError(
                    "staged capability spec capability_id does not match requested spec"
                )
            if capability.spec.version != capability_spec.version:
                raise LoadError(
                    "staged capability spec version does not match requested spec"
                )
            load_id = uuid4().hex
            handle = LoadedCapability(
                load_id=load_id,
                manifest=manifest,
                allocation=allocation,
                workdir=workdir,
                capability=capability,
                _tempdir=tempdir,
            )
            self._active[load_id] = handle
            return handle
        except Exception as exc:
            try:
                tempdir.cleanup()
            finally:
                self._scheduler.release(allocation)
            if isinstance(exc, LoadError):
                raise
            raise LoadError("capability staging failed") from exc

    def unload(self, handle: LoadedCapability) -> None:
        active = self._active.get(handle.load_id)
        if active is None or active is not handle:
            raise KeyError(f"unknown load handle: {handle.load_id}")
        if handle.state is LoaderState.UNLOADED:
            raise LoadError(f"capability {handle.load_id} is already unloaded")

        cleanup_error: BaseException | None = None
        try:
            handle.capability.cleanup()
        except BaseException as exc:
            cleanup_error = exc
        finally:
            try:
                handle._tempdir.cleanup()
            finally:
                self._scheduler.release(handle.allocation)
                handle.state = LoaderState.UNLOADED
                self._active.pop(handle.load_id, None)

        if cleanup_error is not None:
            raise LoadError("capability cleanup failed") from cleanup_error
