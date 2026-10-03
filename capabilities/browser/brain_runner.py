from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from core.brain import StepRunner
from core.router import RouteCandidate

from .agent import BrowserTask
from .cli import PlaywrightCliTransport
from .goal_agent import BrowserGoalAgent, BrowserGoalResult
from .planner import BrowserIntentPlanner


@dataclass(frozen=True, slots=True)
class BrowserBrainOutput:
    """Non-sensitive output returned to the Brain after a browser goal."""

    status: str
    summary: str
    cycles: int
    actions_executed: int
    verification_passed: bool
    confirmation_required: bool
    evidence: tuple[str, ...]


class BrowserGoalStepRunner(StepRunner):
    """Adapt a natural-language Brain step into the closed-loop browser agent."""

    def __init__(
        self,
        *,
        planner: BrowserIntentPlanner,
        session: str = "super-ai-browser",
        profile_dir: Path = Path(".super-ai/browser/profile"),
        workspace_dir: Path = Path(".super-ai/browser/workspace"),
        headed: bool = True,
        max_cycles: int = 12,
        max_actions_per_cycle: int = 4,
        confirmation_callback: Callable[[object], bool] | None = None,
    ) -> None:
        self._planner = planner
        self._session = session
        self._profile_dir = Path(profile_dir)
        self._workspace_dir = Path(workspace_dir)
        self._headed = headed
        self._max_cycles = max_cycles
        self._max_actions_per_cycle = max_actions_per_cycle
        self._confirmation_callback = confirmation_callback

    def run(
        self,
        route: RouteCandidate,
        step,
        context: Mapping[str, object],
    ) -> BrowserBrainOutput:
        if route.entry.manifest.capability_id != "browser.agent":
            raise ValueError(
                "BrowserGoalStepRunner received a non-browser capability route"
            )

        start_url = context.get("__browser_start_url")
        allowed = context.get("__browser_allowed_origins")
        if not isinstance(start_url, str):
            raise ValueError("context requires __browser_start_url")
        if not isinstance(allowed, (list, tuple)) or not all(
            isinstance(item, str) for item in allowed
        ):
            raise ValueError(
                "context requires __browser_allowed_origins as a list/tuple of strings"
            )

        confirmed = bool(context.get("__browser_confirmed", False))
        task = BrowserTask(
            goal=step.description,
            start_url=start_url,
            allowed_origins=tuple(allowed),
            session=self._session,
            profile_dir=self._profile_dir,
            workspace_dir=self._workspace_dir,
            headed=self._headed,
            confirmed=confirmed,
        )

        transport = PlaywrightCliTransport(session=self._session)
        goal_agent = BrowserGoalAgent(
            transport=transport,
            planner=self._planner,
            max_cycles=self._max_cycles,
            max_actions_per_cycle=self._max_actions_per_cycle,
        )
        result: BrowserGoalResult = goal_agent.run(
            task,
            confirmation_callback=self._confirmation_callback,
        )
        return BrowserBrainOutput(
            status=result.status,
            summary=result.summary,
            cycles=result.cycles,
            actions_executed=result.actions_executed,
            verification_passed=result.verification_passed,
            confirmation_required=result.confirmation_required,
            evidence=result.evidence,
        )
