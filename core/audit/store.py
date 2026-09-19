from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any, Mapping


class AuditError(RuntimeError):
    """Raised when an audit record is invalid or integrity verification fails."""


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    timestamp: str
    event_name: str
    attributes: Mapping[str, Any]
    previous_hash: str
    event_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_name": self.event_name,
            "attributes": dict(self.attributes),
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }


class HashChainAuditStore:
    """Small append-only hash-chain audit store with bounded event payloads."""

    _HASH_RE = re.compile(r"^[0-9a-f]{64}$")

    def __init__(self, path: Path, *, max_event_bytes: int = 16 * 1024) -> None:
        if max_event_bytes <= 0:
            raise ValueError("max_event_bytes must be > 0")
        self._path = Path(path)
        self._max_event_bytes = max_event_bytes
        self._lock = RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        event_name: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        if not event_name or event_name.strip() != event_name:
            raise AuditError("event_name must be non-empty and trimmed")
        safe_attributes = _sanitize_mapping(attributes or {})
        with self._lock:
            previous_hash, sequence = self._tail_locked()
            timestamp = datetime.now(timezone.utc).isoformat()
            unsigned = {
                "sequence": sequence,
                "timestamp": timestamp,
                "event_name": event_name,
                "attributes": safe_attributes,
                "previous_hash": previous_hash,
            }
            event_hash = _hash_record(unsigned)
            event = AuditEvent(
                sequence=sequence,
                timestamp=timestamp,
                event_name=event_name,
                attributes=safe_attributes,
                previous_hash=previous_hash,
                event_hash=event_hash,
            )
            encoded = (
                json.dumps(
                    event.as_dict(),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")
            if len(encoded) > self._max_event_bytes:
                raise AuditError("audit event exceeds size limit")
            with self._path.open("ab") as handle:
                handle.write(encoded)
            return event

    def read_all(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            if not self._path.exists():
                return ()
            events = []
            for line_number, line in enumerate(
                self._path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuditError(
                        f"audit log line {line_number} is invalid JSON"
                    ) from exc
                events.append(_event_from_payload(payload))
            return tuple(events)

    def verify(self) -> bool:
        previous_hash = _GENESIS_HASH
        expected_sequence = 1
        for event in self.read_all():
            if event.sequence != expected_sequence:
                raise AuditError("audit sequence is not contiguous")
            if event.previous_hash != previous_hash:
                raise AuditError("audit hash chain is broken")
            unsigned = {
                "sequence": event.sequence,
                "timestamp": event.timestamp,
                "event_name": event.event_name,
                "attributes": dict(event.attributes),
                "previous_hash": event.previous_hash,
            }
            expected_hash = _hash_record(unsigned)
            if event.event_hash != expected_hash:
                raise AuditError("audit event hash mismatch")
            previous_hash = event.event_hash
            expected_sequence += 1
        return True

    def _tail_locked(self) -> tuple[str, int]:
        events = self.read_all()
        if not events:
            return _GENESIS_HASH, 1
        last = events[-1]
        if not self._HASH_RE.fullmatch(last.event_hash):
            raise AuditError("audit tail has an invalid hash")
        return last.event_hash, last.sequence + 1


def _event_from_payload(payload: Any) -> AuditEvent:
    if not isinstance(payload, dict):
        raise AuditError("audit event must be an object")
    required = (
        "sequence",
        "timestamp",
        "event_name",
        "attributes",
        "previous_hash",
        "event_hash",
    )
    if any(key not in payload for key in required):
        raise AuditError("audit event is missing required fields")
    sequence = payload["sequence"]
    if not isinstance(sequence, int) or sequence <= 0:
        raise AuditError("audit sequence must be a positive integer")
    for key in ("timestamp", "event_name", "previous_hash", "event_hash"):
        if not isinstance(payload[key], str):
            raise AuditError(f"audit field {key!r} must be a string")
    if not isinstance(payload["attributes"], dict):
        raise AuditError("audit attributes must be an object")
    return AuditEvent(
        sequence=sequence,
        timestamp=payload["timestamp"],
        event_name=payload["event_name"],
        attributes=_sanitize_mapping(payload["attributes"]),
        previous_hash=payload["previous_hash"],
        event_hash=payload["event_hash"],
    )


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or "\n" in key or "\r" in key:
            raise AuditError("audit attribute keys must be non-empty single-line strings")
        if isinstance(item, (str, int, float, bool)) or item is None:
            if isinstance(item, str) and ("\n" in item or "\r" in item):
                raise AuditError("audit attribute strings must be single-line")
            result[key] = item
        elif isinstance(item, (list, tuple)):
            result[key] = [_sanitize_value(x) for x in item]
        elif isinstance(item, dict):
            result[key] = _sanitize_mapping(item)
        else:
            raise AuditError(f"unsupported audit attribute type for {key!r}")
    return result


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and ("\n" in value or "\r" in value):
            raise AuditError("audit attribute strings must be single-line")
        return value
    if isinstance(value, dict):
        return _sanitize_mapping(value)
    raise AuditError("unsupported nested audit attribute type")


def _hash_record(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_GENESIS_HASH = "0" * 64
