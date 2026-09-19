from __future__ import annotations

from threading import Event, Lock


class CancellationToken:
    """Thread-safe one-shot cancellation signal for an execution."""

    _MAX_REASON_LENGTH = 256

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason: str | None = None

    def cancel(self, reason: str = "cancelled by caller") -> bool:
        """Request cancellation once; return True only for the first request."""
        normalized = str(reason).strip()
        if not normalized:
            normalized = "cancelled by caller"
        normalized = normalized[: self._MAX_REASON_LENGTH]

        with self._lock:
            if self._event.is_set():
                return False
            self._reason = normalized
            self._event.set()
            return True

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason
