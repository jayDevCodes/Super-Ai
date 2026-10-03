#!/usr/bin/env python3
"""Exercise the 1,000-unit task catalog without downloading models."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models.task_catalog import TaskCatalog


def main() -> int:
    catalog = TaskCatalog()
    print(f"Super-Ai task catalog: {len(catalog.units)} independently routable units")
    for task_id in (
        "text.extract.structured",
        "code.recover.failure",
        "browser.execute.privacy",
        "retrieval.analyze.quality",
        "video.verify.duration" if False else "video.verify.quality",
    ):
        unit = catalog.get(task_id)
        print(f"- {unit.task_id}: {unit.runtime} -> {unit.model}; {unit.verification}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
