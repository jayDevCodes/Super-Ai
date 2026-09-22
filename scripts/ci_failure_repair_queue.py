#!/usr/bin/env python3
"""Turn a GitHub Actions test log into a stable one-root-cause-at-a-time repair queue."""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_LOG_PREFIX_RE = re.compile(r"^\ufeff?\d{4}-\d{2}-\d{2}T[^ ]+Z\s*")
_TEST_RE = re.compile(
    r"^(?:.*?\b)?(?:ERROR|FAIL): "
    r"(?P<method>[A-Za-z0-9_]+) \((?P<test>[A-Za-z0-9_.]+)\)$"
)
_EXCEPTION_RE = re.compile(
    r"^(?:[A-Za-z_][\w]*\.)?"
    r"(?P<kind>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Interrupt))"
    r": (?P<message>.*)$"
)

def normalize(line: str) -> str:
    line = _ANSI_RE.sub("", line)
    line = _LOG_PREFIX_RE.sub("", line)
    return line.strip()

def parse_failures(lines: Iterable[str]) -> list[dict[str, object]]:
    groups: OrderedDict[str, dict[str, object]] = OrderedDict()
    current_test: str | None = None
    for raw in lines:
        line = normalize(raw)
        if not line:
            continue
        match = _TEST_RE.match(line)
        if match:
            current_test = match.group("test")
            continue
        if current_test is None:
            continue
        exception = _EXCEPTION_RE.match(line)
        if exception:
            signature = f'{exception.group("kind")}: {exception.group("message")[:300]}'
            group = groups.setdefault(
                signature,
                {"status": "unresolved", "root_cause": signature, "tests": []},
            )
            tests = group["tests"]
            assert isinstance(tests, list)
            if current_test not in tests:
                tests.append(current_test)
            current_test = None
    return [
        {"issue_id": f"CI-{index:03d}", **group}
        for index, group in enumerate(groups.values(), start=1)
    ]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8", errors="replace")
    document = {
        "schema_version": 1,
        "policy": {
            "ordering": "first-observed-root-cause",
            "advance_gate": "current-root-cause-must-be-green-before-next-root-cause",
            "cascade_handling": "same-exception-signature-is-one-issue",
            "resolution_claim": "never-inferred-from-parsing",
        },
        "issues": parse_failures(source.splitlines()),
    }
    args.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
