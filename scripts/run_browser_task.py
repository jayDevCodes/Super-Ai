#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

from capabilities.browser.agent import BrowserAction, BrowserAgent, BrowserTask
from capabilities.browser.cli import PlaywrightCliTransport


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one Super-Ai browser task through the first-party Playwright adapter."
    )
    parser.add_argument("task_file", type=Path, help="JSON file containing a BrowserTask mapping")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="explicitly approve consequential browser actions in this run",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(args.task_file.read_text(encoding="utf-8"))
        task = BrowserTask(
            goal=str(payload["goal"]),
            start_url=str(payload["start_url"]),
            actions=tuple(
                BrowserAction(**action)
                for action in payload.get("actions", [])
            ),
            allowed_origins=tuple(str(item) for item in payload["allowed_origins"]),
            session=str(payload.get("session", "super-ai-browser")),
            profile_dir=Path(payload.get("profile_dir", ".super-ai/browser/profile")),
            workspace_dir=Path(payload.get("workspace_dir", ".super-ai/browser/workspace")),
            headed=bool(payload.get("headed", True)),
            confirmed=False,
        )
        if args.confirm:
            task = replace(task, confirmed=True)

        transport = PlaywrightCliTransport(session=task.session)
        result = BrowserAgent(transport).execute(task)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"success": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
