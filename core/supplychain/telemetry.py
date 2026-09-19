from __future__ import annotations

from dataclasses import dataclass
import threading


@dataclass(frozen=True, slots=True)
class SupplyChainMetrics:
    admitted: int
    rejected: int
    verified: int
    registry_syncs: int


class SupplyChainTelemetry:
    def __init__(self) -> None:
        self._lock=threading.Lock()
        self._admitted=0
        self._rejected=0
        self._verified=0
        self._syncs=0

    def record_admission(self, accepted: bool) -> None:
        with self._lock:
            if accepted:
                self._admitted+=1
            else:
                self._rejected+=1

    def record_verification(self, verified: bool) -> None:
        if verified:
            with self._lock:
                self._verified+=1

    def record_sync(self) -> None:
        with self._lock:
            self._syncs+=1

    def snapshot(self) -> SupplyChainMetrics:
        with self._lock:
            return SupplyChainMetrics(self._admitted,self._rejected,self._verified,self._syncs)
