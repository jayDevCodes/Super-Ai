#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from capabilities.browser.agent import BrowserTask
from capabilities.browser.cli import PlaywrightCliTransport
from capabilities.browser.goal_agent import BrowserGoalAgent
from capabilities.browser.planner import OllamaBrowserIntentPlanner
from core.models import TaskModelManager


def _confirm(plan) -> bool:
    print("\nSuper-Ai wants to perform a consequential browser action.")
    if plan.confirmation_reason:
        print(f"Reason: {plan.confirmation_reason}")
    for index, action in enumerate(plan.actions, start=1):
        target = action.target or action.url or ""
        print(f"  {index}. {action.kind}" + (f" -> {target}" if target else ""))
    answer = input("Approve this action? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a natural-language Super-Ai browser goal."
    )
    parser.add_argument("goal", help="plain-language browser task")
    parser.add_argument("--start-url", required=True)
    parser.add_argument(
        "--allowed-origin",
        action="append",
        required=True,
        dest="allowed_origins",
        help="repeat for every HTTPS origin the task is allowed to visit",
    )
    parser.add_argument("--session", default="super-ai-browser")
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(".super-ai/browser/profile"),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".super-ai/browser/workspace"),
    )
    parser.add_argument("--model")
    parser.add_argument("--ollama-url")
    parser.add_argument("--max-cycles", type=int, default=12)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="pre-approve consequential actions for this goal",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run Chrome without opening a visible window",
    )
    args = parser.parse_args()

    try:
        task = BrowserTask(
            goal=args.goal,
            start_url=args.start_url,
            allowed_origins=tuple(args.allowed_origins),
            session=args.session,
            profile_dir=args.profile,
            workspace_dir=args.workspace,
            headed=not args.headless,
            confirmed=args.confirm,
        )
        manager = TaskModelManager(base_url=args.ollama_url)

        if args.model:
            selection = manager.selection_for_model(args.model)
        else:
            selection = manager.select(args.goal)

        with manager.use(selection):
            planner = OllamaBrowserIntentPlanner(
                model=selection.model,
                base_url=args.ollama_url,
            )
            transport = PlaywrightCliTransport(session=args.session)
            agent = BrowserGoalAgent(
                transport=transport,
                planner=planner,
                max_cycles=args.max_cycles,
            )
            result = agent.run(
                task,
                confirmation_callback=None if args.confirm else _confirm,
            )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 2
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
