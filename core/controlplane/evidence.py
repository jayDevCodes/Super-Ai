from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ControlEvidence:
    control: str
    status: str
    fingerprint: str
    attributes: tuple[tuple[str, str], ...]


def make_evidence(control: str, status: str, attributes: Mapping[str, object]) -> ControlEvidence:
    if not control or not status:
        raise ValueError("control and status are required")
    normalized=tuple(sorted((str(k), str(v)) for k,v in attributes.items()))
    material={"control":control,"status":status,"attributes":normalized}
    digest=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return ControlEvidence(control,status,digest,normalized)
