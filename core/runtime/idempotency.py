from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import threading
import time
from typing import Mapping

from .execution import ExecutionResult


class IdempotencyError(RuntimeError):
    """Base error for execution idempotency coordination."""


class IdempotencyConflictError(IdempotencyError):
    """Raised when one key is reused with a different request fingerprint."""


class IdempotencyClaimError(IdempotencyError):
    """Raised when an idempotency claim lifecycle is misused."""


@dataclass(frozen=True, slots=True)
class IdempotencyReplay:
    """A completed execution result safe to replay for a duplicate request."""

    key: str
    fingerprint: str
    result: ExecutionResult


class IdempotencyClaim:
    """One ownership claim over an idempotency key."""

    def __init__(
        self,
        coordinator: "IdempotencyCoordinator",
        *,
        key: str,
        fingerprint: str,
        owner: bool,
        replay: IdempotencyReplay | None = None,
    ) -> None:
        self._coordinator = coordinator
        self.key = key
        self.fingerprint = fingerprint
        self.owner = owner
        self.replay = replay
        self._finished = False

    def complete(self, result: ExecutionResult) -> None:
        if not self.owner:
            raise IdempotencyClaimError("replay claims cannot be completed")
        if self._finished:
            raise IdempotencyClaimError("idempotency claim is already finished")
        self._coordinator.complete(self.key, self.fingerprint, result)
        self._finished = True

    def abort(self) -> None:
        if not self.owner or self._finished:
            return
        self._coordinator.abort(self.key, self.fingerprint)
        self._finished = True

    def __enter__(self) -> "IdempotencyClaim":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.abort()
        elif self.owner and not self._finished:
            self.abort()


@dataclass
class _Entry:
    fingerprint: str
    completed_result: ExecutionResult | None
    event: threading.Event
    created_at: float


class IdempotencyCoordinator:
    """Process-local exactly-once coordinator for one execution request key.

    A caller owns the first claim for a key. Concurrent callers wait for that
    claim to finish and then replay its terminal result. Reusing a completed
    key with a different fingerprint is rejected. Completed entries are bounded
    by count and age; persistence across process restarts is intentionally a
    later hardening concern.
    """

    def __init__(
        self,
        *,
        max_entries: int = 128,
        ttl_seconds: float = 3600.0,
        replay_output_bytes: int = 64 * 1024,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if replay_output_bytes <= 0:
            raise ValueError("replay_output_bytes must be > 0")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._replay_output_bytes = replay_output_bytes
        self._lock = threading.RLock()
        self._entries: OrderedDict[str, _Entry] = OrderedDict()

    def claim(self, key: str | None, fingerprint: str) -> IdempotencyClaim:
        """Claim a key or wait for/replay an existing identical request."""
        _validate_fingerprint(fingerprint)
        if key is None:
            return IdempotencyClaim(
                self,
                key="",
                fingerprint=fingerprint,
                owner=True,
            )
        normalized_key = _validate_key(key)
        while True:
            with self._lock:
                self._purge_expired_locked()
                entry = self._entries.get(normalized_key)
                if entry is None:
                    entry = _Entry(
                        fingerprint=fingerprint,
                        completed_result=None,
                        event=threading.Event(),
                        created_at=time.monotonic(),
                    )
                    self._entries[normalized_key] = entry
                    return IdempotencyClaim(
                        self,
                        key=normalized_key,
                        fingerprint=fingerprint,
                        owner=True,
                    )

                if entry.fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for a different request"
                    )

                if entry.completed_result is not None:
                    self._entries.move_to_end(normalized_key)
                    return IdempotencyClaim(
                        self,
                        key=normalized_key,
                        fingerprint=fingerprint,
                        owner=False,
                        replay=IdempotencyReplay(
                            key=normalized_key,
                            fingerprint=fingerprint,
                            result=entry.completed_result,
                        ),
                    )

                event = entry.event

            event.wait(timeout=self._ttl_seconds)
            if not event.is_set():
                with self._lock:
                    current = self._entries.get(normalized_key)
                    if current is entry and current.completed_result is None:
                        raise IdempotencyClaimError(
                            "idempotency claim did not complete before its wait deadline"
                        )

    def complete(self, key: str, fingerprint: str, result: ExecutionResult) -> None:
        if not key:
            return
        _validate_fingerprint(fingerprint)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.fingerprint != fingerprint:
                raise IdempotencyClaimError("idempotency claim is no longer active")
            if entry.completed_result is not None:
                raise IdempotencyClaimError("idempotency claim is already completed")
            entry.completed_result = _bounded_result(
                result,
                max_output_bytes=self._replay_output_bytes,
            )
            entry.event.set()
            self._entries.move_to_end(key)
            self._trim_locked()

    def abort(self, key: str, fingerprint: str) -> None:
        if not key:
            return
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.fingerprint != fingerprint:
                return
            if entry.completed_result is not None:
                return
            self._entries.pop(key, None)
            entry.event.set()

    def size(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            return len(self._entries)

    def _purge_expired_locked(self) -> None:
        cutoff = time.monotonic() - self._ttl_seconds
        expired = [
            key
            for key, entry in self._entries.items()
            if entry.completed_result is not None and entry.created_at < cutoff
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _trim_locked(self) -> None:
        self._purge_expired_locked()
        while len(self._entries) > self._max_entries:
            key, entry = next(iter(self._entries.items()))
            if entry.completed_result is None:
                self._entries.move_to_end(key)
                if all(
                    item.completed_result is None
                    for item in self._entries.values()
                ):
                    return
                continue
            self._entries.pop(key, None)


def request_fingerprint(
    *,
    capability_id: str,
    version: str,
    image: str,
    command: tuple[str, ...],
    expected_image_digest: str | None,
    workspace_root: str,
    output_path: str,
    timeout_seconds: float,
    network: str,
    max_processes: int = 64,
    max_open_files: int = 1024,
    output_contract: Mapping[str, object] = None,
) -> str:
    """Hash stable execution semantics; volatile trace/cancellation data is excluded."""
    if output_contract is None:
        raise ValueError("output_contract must be provided")
    payload = {
        "capability_id": capability_id,
        "version": version,
        "image": image,
        "command": list(command),
        "expected_image_digest": expected_image_digest,
        "workspace_root": workspace_root,
        "output_path": output_path,
        "timeout_seconds": timeout_seconds,
        "network": network,
        "max_processes": max_processes,
        "max_open_files": max_open_files,
        "output_contract": dict(output_contract),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_key(key: str) -> str:
    normalized = str(key).strip()
    if not normalized:
        raise ValueError("idempotency_key must not be empty")
    if len(normalized) > 255:
        raise ValueError("idempotency_key must be <= 255 characters")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in normalized):
        raise ValueError("idempotency_key must not contain control characters")
    return normalized


def _validate_fingerprint(fingerprint: str) -> None:
    if not fingerprint or len(fingerprint) != 64:
        raise ValueError("fingerprint must be a sha256 hex digest")
    try:
        int(fingerprint, 16)
    except ValueError as exc:
        raise ValueError("fingerprint must be a sha256 hex digest") from exc


def _bounded_result(
    result: ExecutionResult,
    *,
    max_output_bytes: int,
) -> ExecutionResult:
    stdout = result.stdout
    stderr = result.stderr
    stdout_truncated = result.stdout_truncated
    stderr_truncated = result.stderr_truncated

    if len(stdout.encode("utf-8")) > max_output_bytes:
        stdout = _truncate_utf8(stdout, max_output_bytes)
        stdout_truncated = True
    if len(stderr.encode("utf-8")) > max_output_bytes:
        stderr = _truncate_utf8(stderr, max_output_bytes)
        stderr_truncated = True

    telemetry: Mapping[str, object] | None = None
    if result.telemetry is not None:
        telemetry = dict(result.telemetry)

    return ExecutionResult(
        status=result.status,
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=result.duration_seconds,
        timed_out=result.timed_out,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        verified=result.verified,
        cleanup_completed=result.cleanup_completed,
        sandbox_attested=result.sandbox_attested,
        sandbox_image_digest=result.sandbox_image_digest,
        telemetry=telemetry,
        cancellation_reason=result.cancellation_reason,
        output_inspection=result.output_inspection,
    )


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")[:max_bytes]
    while True:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError:
            encoded = encoded[:-1]
