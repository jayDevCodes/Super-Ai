from __future__ import annotations

from dataclasses import dataclass

from .models import RevocationEntry


@dataclass(frozen=True, slots=True)
class RevocationIndex:
    entries: tuple[RevocationEntry, ...] = ()

    def __post_init__(self) -> None:
        for entry in self.entries:
            entry.validate()

    def is_revoked(self, subject: str, *, now_epoch: int) -> bool:
        for entry in self.entries:
            if entry.subject != subject:
                continue
            if entry.expires_at_epoch is None or now_epoch < entry.expires_at_epoch:
                return True
        return False

    def active(self, *, now_epoch: int) -> tuple[RevocationEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.expires_at_epoch is None or now_epoch < entry.expires_at_epoch
        )
