from __future__ import annotations

from dataclasses import dataclass, replace
import re
from secrets import token_hex


_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_RE = re.compile(r"^[0-9a-f]{16}$")


class TraceContextError(ValueError):
    """Raised when trace context does not satisfy the propagation contract."""


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Immutable execution correlation context aligned with W3C/OpenTelemetry IDs."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: str = "00"

    def __post_init__(self) -> None:
        if not _TRACE_ID_RE.fullmatch(self.trace_id) or set(self.trace_id) == {"0"}:
            raise TraceContextError("trace_id must be 32 lowercase hex characters and non-zero")
        if not _SPAN_ID_RE.fullmatch(self.span_id) or set(self.span_id) == {"0"}:
            raise TraceContextError("span_id must be 16 lowercase hex characters and non-zero")
        if self.parent_span_id is not None and not _SPAN_ID_RE.fullmatch(self.parent_span_id):
            raise TraceContextError("parent_span_id must be 16 lowercase hex characters")
        if not re.fullmatch(r"[0-9a-f]{2}", self.trace_flags):
            raise TraceContextError("trace_flags must be two lowercase hex characters")

    @classmethod
    def new_root(cls) -> "TraceContext":
        return cls(trace_id=token_hex(16), span_id=token_hex(8))

    def child(self) -> "TraceContext":
        return replace(
            self,
            span_id=token_hex(8),
            parent_span_id=self.span_id,
        )

    def as_attributes(self) -> dict[str, str]:
        values = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "trace_flags": self.trace_flags,
        }
        if self.parent_span_id is not None:
            values["parent_span_id"] = self.parent_span_id
        return values
