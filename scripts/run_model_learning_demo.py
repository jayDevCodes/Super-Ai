#!/usr/bin/env python3
"""Run deterministic routing lessons without downloading any model weights."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import SpecialistModelRegistry, TaskModelManager


def main() -> int:
    lessons = (
        ("short extraction", "Extract a short label from this text", 1000, 500),
        ("classification", "Classify this short message into one label", 1200, 1000),
        ("code repair", "Repair this code bug and explain the patch", 2000, 1200),
        ("browser", "Browse a page and extract the title", 1600, 1200),
    )
    manager = TaskModelManager()
    print("Super-Ai routing lessons (no weights are downloaded):")
    for label, goal, ram, disk in lessons:
        selection = manager.select(goal, max_ram_mb=ram, max_disk_mb=disk)
        print(f"- {label}: {selection.model} ({selection.reason})")
    specialist = SpecialistModelRegistry().select(
        "embedding", max_ram_mb=1000, max_disk_mb=500,
    )
    print(f"- retrieval memory: {specialist.spec.name} ({specialist.reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
