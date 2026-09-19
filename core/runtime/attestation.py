from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping


class AttestationError(RuntimeError):
    """Raised when a container's observed configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class AttestationPolicy:
    """Expected security and resource properties for one sandbox."""

    expected_memory_bytes: int
    expected_cpus: int
    expected_image_digest: str | None = None
    expected_user: str = "65532:65532"
    required_mounts: tuple[str, ...] = ("/capability", "/workspace")
    require_read_only_root: bool = True
    require_drop_all_capabilities: bool = True

    def validate(self) -> None:
        if self.expected_memory_bytes <= 0:
            raise ValueError("expected_memory_bytes must be > 0")
        if self.expected_cpus <= 0:
            raise ValueError("expected_cpus must be > 0")
        if self.expected_image_digest is not None and not _DIGEST_RE.fullmatch(
            self.expected_image_digest
        ):
            raise ValueError("expected_image_digest must be sha256:<64 hex>")
        if not _USER_RE.fullmatch(self.expected_user):
            raise ValueError("expected_user contains unsupported characters")
        if not self.required_mounts:
            raise ValueError("required_mounts must not be empty")


@dataclass(frozen=True, slots=True)
class SandboxAttestation:
    """Immutable evidence that the created container matched policy."""

    container_id: str
    image_reference: str
    image_digest: str | None
    cpus: int
    memory_bytes: int
    read_only_root: bool
    cap_drop: tuple[str, ...]
    user: str | None
    network_count: int
    mount_destinations: tuple[str, ...]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "container_id": self.container_id,
            "image_reference": self.image_reference,
            "image_digest": self.image_digest,
            "cpus": self.cpus,
            "memory_bytes": self.memory_bytes,
            "read_only_root": self.read_only_root,
            "cap_drop": list(self.cap_drop),
            "user": self.user,
            "network_count": self.network_count,
            "mount_destinations": list(self.mount_destinations),
            "passed": self.passed,
        }


def attest_container(
    payload: bytes | str | Mapping[str, Any],
    *,
    container_id: str,
    image_reference: str,
    policy: AttestationPolicy,
    network_disabled: bool,
) -> SandboxAttestation:
    """Parse Apple Container inspect JSON and fail closed on mismatch."""
    policy.validate()
    document = _decode_document(payload)
    if not isinstance(document, list) or len(document) != 1:
        raise AttestationError("container inspect must return exactly one container")

    item = document[0]
    if not isinstance(item, dict):
        raise AttestationError("container inspect entry must be an object")

    configuration = item.get("configuration")
    if not isinstance(configuration, dict):
        raise AttestationError("inspect result is missing configuration")

    observed_id = configuration.get("id")
    if observed_id != container_id:
        raise AttestationError("container ID mismatch")

    image = configuration.get("image")
    if not isinstance(image, dict):
        raise AttestationError("inspect result is missing image identity")

    observed_reference = image.get("reference")
    if observed_reference != image_reference:
        raise AttestationError(
            f"image reference mismatch: expected {image_reference!r}, got {observed_reference!r}"
        )

    descriptor = image.get("descriptor")
    if not isinstance(descriptor, dict):
        raise AttestationError("inspect result is missing image descriptor")

    observed_digest = descriptor.get("digest")
    if not isinstance(observed_digest, str):
        raise AttestationError("inspect result is missing image digest")

    if policy.expected_image_digest is not None:
        if observed_digest != policy.expected_image_digest:
            raise AttestationError(
                "container image digest does not match the pinned expected digest"
            )

    resources = configuration.get("resources")
    if not isinstance(resources, dict):
        raise AttestationError("inspect result is missing resources")

    cpus = resources.get("cpus")
    memory_bytes = resources.get("memoryInBytes")
    if not isinstance(cpus, int) or isinstance(cpus, bool):
        raise AttestationError("inspect result has invalid CPU allocation")
    if not isinstance(memory_bytes, int) or isinstance(memory_bytes, bool):
        raise AttestationError("inspect result has invalid memory allocation")

    if cpus != policy.expected_cpus:
        raise AttestationError(
            f"CPU allocation mismatch: expected {policy.expected_cpus}, got {cpus}"
        )
    if memory_bytes != policy.expected_memory_bytes:
        raise AttestationError(
            "memory allocation mismatch: "
            f"expected {policy.expected_memory_bytes}, got {memory_bytes}"
        )

    read_only_root = configuration.get("readOnly")
    if not isinstance(read_only_root, bool):
        raise AttestationError("inspect result has invalid readOnly value")
    if policy.require_read_only_root and not read_only_root:
        raise AttestationError("container root filesystem is not read-only")

    cap_drop_raw = configuration.get("capDrop")
    if not isinstance(cap_drop_raw, list) or not all(
        isinstance(value, str) for value in cap_drop_raw
    ):
        raise AttestationError("inspect result has invalid capDrop")
    cap_drop = tuple(cap_drop_raw)
    if policy.require_drop_all_capabilities and "ALL" not in cap_drop:
        raise AttestationError("container does not drop ALL capabilities")

    init_process = configuration.get("initProcess")
    if not isinstance(init_process, dict):
        raise AttestationError("inspect result is missing initProcess")
    observed_user = _user_description(init_process.get("user"))
    if policy.expected_user != observed_user:
        raise AttestationError(
            f"container user mismatch: expected {policy.expected_user!r}, got {observed_user!r}"
        )

    mounts_raw = configuration.get("mounts")
    if not isinstance(mounts_raw, list):
        raise AttestationError("inspect result is missing mounts")

    destinations: list[str] = []
    mount_by_destination: dict[str, dict[str, Any]] = {}
    for mount in mounts_raw:
        if not isinstance(mount, dict):
            raise AttestationError("inspect result contains an invalid mount")
        destination = mount.get("destination")
        options = mount.get("options")
        if not isinstance(destination, str) or not isinstance(options, list):
            raise AttestationError("inspect result contains an invalid mount record")
        if not all(isinstance(option, str) for option in options):
            raise AttestationError("inspect result contains invalid mount options")
        destinations.append(destination)
        mount_by_destination[destination] = mount

    required = set(policy.required_mounts)
    if set(destinations) != required:
        raise AttestationError(
            f"mount destinations mismatch: expected {sorted(required)}, "
            f"got {sorted(set(destinations))}"
        )

    capability_mount = mount_by_destination["/capability"]
    if "ro" not in capability_mount["options"]:
        raise AttestationError("capability mount is not read-only")

    workspace_mount = mount_by_destination["/workspace"]
    if "ro" in workspace_mount["options"]:
        raise AttestationError("workspace mount must remain writable")

    status = item.get("status")
    if not isinstance(status, dict):
        raise AttestationError("inspect result is missing status")

    networks = status.get("networks")
    if not isinstance(networks, list):
        raise AttestationError("inspect result has invalid network status")

    network_count = len(networks)
    if network_disabled and network_count != 0:
        raise AttestationError(
            "disabled-network container unexpectedly has network attachments"
        )

    return SandboxAttestation(
        container_id=container_id,
        image_reference=image_reference,
        image_digest=observed_digest,
        cpus=cpus,
        memory_bytes=memory_bytes,
        read_only_root=read_only_root,
        cap_drop=cap_drop,
        user=observed_user,
        network_count=network_count,
        mount_destinations=tuple(sorted(set(destinations))),
        passed=True,
    )


def _decode_document(payload: bytes | str | Mapping[str, Any]) -> Any:
    if isinstance(payload, dict):
        return payload
    try:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError("container inspect output is not valid JSON") from exc


def _user_description(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    user_id = value.get("id")
    if isinstance(user_id, dict):
        uid = user_id.get("uid")
        gid = user_id.get("gid")
        if isinstance(uid, int) and isinstance(gid, int):
            return f"{uid}:{gid}"
    raw = value.get("raw")
    if isinstance(raw, str):
        return raw
    return None


_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
_USER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
