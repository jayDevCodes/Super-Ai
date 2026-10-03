from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from pathlib import Path
from typing import Callable

from .agent import BrowserAction, BrowserAgent, BrowserTask
from .cli import PlaywrightCliTransport
from .planner import (
    BrowserIntentPlanner,
    BrowserObservation,
    BrowserPlan,
    BrowserPlannerError,
    BrowserVerification,
)


class BrowserGoalAgentError(RuntimeError):
    """Raised when an autonomous browser goal cannot continue safely."""


@dataclass(frozen=True, slots=True)
class BrowserGoalResult:
    status: str
    goal: str
    summary: str
    cycles: int
    actions_executed: int
    verification_passed: bool
    confirmation_required: bool = False
    confirmation_reason: str = ""
    error: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)


class BrowserGoalAgent:
    """Closed-loop natural-language browser agent over the first-party BrowserAgent."""

    def __init__(
        self,
        *,
        transport: PlaywrightCliTransport,
        planner: BrowserIntentPlanner,
        max_cycles: int = 12,
        max_actions_per_cycle: int = 1,
    ) -> None:
        if max_cycles <= 0:
            raise ValueError("max_cycles must be > 0")
        if max_actions_per_cycle != 1:
            raise ValueError(
                "max_actions_per_cycle must be exactly 1 so accessibility refs are always fresh"
            )
        self._transport = transport
        self._planner = planner
        self._max_cycles = max_cycles
        self._max_actions_per_cycle = max_actions_per_cycle

    def run(
        self,
        task: BrowserTask,
        *,
        confirmation_callback: Callable[[BrowserPlan], bool] | None = None,
    ) -> BrowserGoalResult:
        task.validate()
        if not task.actions:
            return self._run_natural_goal(
                task,
                confirmation_callback=confirmation_callback,
            )
        raise BrowserGoalAgentError(
            "BrowserGoalAgent accepts a natural-language goal without a fixed action list"
        )

    def _run_natural_goal(
        self,
        task: BrowserTask,
        *,
        confirmation_callback: Callable[[BrowserPlan], bool] | None,
    ) -> BrowserGoalResult:
        self._prepare_directories(task)
        outputs: list[str] = []
        history: list[str] = []
        evidence: list[str] = []
        action_count = 0
        last_fingerprint: str | None = None

        try:
            opened = self._transport.open(
                task.start_url,
                persistent=True,
                profile=task.profile_dir.expanduser().resolve(),
                headed=task.headed,
                browser="chrome",
            )
            outputs.append(opened.stdout)

            for cycle in range(1, self._max_cycles + 1):
                observation = self._observe(task)
                state_fingerprint = _fingerprint(observation.url, observation.snapshot)
                if state_fingerprint == last_fingerprint:
                    history.append("state unchanged after previous cycle")
                last_fingerprint = state_fingerprint

                plan = self._planner.plan(
                    task.goal,
                    observation,
                    history=tuple(history),
                )
                plan.validate(max_actions=self._max_actions_per_cycle)

                risky = plan.needs_confirmation or any(
                    action.consequential for action in plan.actions
                )
                risky = risky or _goal_requires_confirmation(task.goal)

                plan_approved = task.confirmed
                if risky and not task.confirmed:
                    plan_approved = (
                        confirmation_callback(plan)
                        if confirmation_callback is not None
                        else False
                    )
                    if not plan_approved:
                        return BrowserGoalResult(
                            status="confirmation_required",
                            goal=task.goal,
                            summary=plan.confirmation_reason or plan.summary,
                            cycles=cycle,
                            actions_executed=action_count,
                            verification_passed=False,
                            confirmation_required=True,
                            confirmation_reason=(
                                plan.confirmation_reason
                                or "the goal contains a consequential action"
                            ),
                            evidence=tuple(evidence),
                        )

                if plan.done:
                    passed, matched = _verify(observation, plan.verification)
                    if not passed:
                        raise BrowserGoalAgentError(
                            "planner claimed completion but deterministic verification failed"
                        )
                    evidence.extend(matched)
                    return BrowserGoalResult(
                        status="completed",
                        goal=task.goal,
                        summary=plan.summary,
                        cycles=cycle,
                        actions_executed=action_count,
                        verification_passed=True,
                        evidence=tuple(dict.fromkeys(evidence)),
                    )

                if not plan.actions:
                    raise BrowserGoalAgentError(
                        "planner returned neither actions nor a completed state"
                    )

                for action in plan.actions:
                    if action.consequential and not plan_approved:
                        plan_approved = (
                            confirmation_callback(plan)
                            if confirmation_callback is not None
                            else False
                        )
                        if not plan_approved:
                            return BrowserGoalResult(
                                status="confirmation_required",
                                goal=task.goal,
                                summary=plan.summary,
                                cycles=cycle,
                                actions_executed=action_count,
                                verification_passed=False,
                                confirmation_required=True,
                                confirmation_reason=(
                                    plan.confirmation_reason
                                    or "a consequential browser action requires approval"
                                ),
                                evidence=tuple(evidence),
                            )

                    result = self._run_action(task, action)
                    action_count += 1
                    outputs.append(result.stdout)
                    history.append(_safe_history_line(action, result.stdout))
                    if len(history) > 12:
                        del history[:-12]
                    self._assert_current_origin(task)

                    # Playwright invalidates accessibility refs when the page changes.
                    # Stop after one action so the next cycle always plans from fresh state.
                    break

                post = self._observe(task)
                if plan.verification.text or plan.verification.url_contains:
                    passed, matched = _verify(post, plan.verification)
                    if passed:
                        evidence.extend(matched)
                    else:
                        history.append("planned verification was not yet satisfied")

            raise BrowserGoalAgentError(
                "maximum browser planning cycles reached without verified completion"
            )
        except BrowserGoalAgentError:
            raise
        except BrowserPlannerError:
            raise
        except Exception as exc:
            raise BrowserGoalAgentError(
                f"browser goal failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _observe(self, task: BrowserTask) -> BrowserObservation:
        current = self._transport.current_url().stdout.strip()
        if not current or not task.origin_allowed(current):
            raise BrowserGoalAgentError(
                "current browser URL is empty or outside the allowed origin list"
            )
        snapshot = self._transport.snapshot().stdout
        return BrowserObservation(
            url=current,
            snapshot=snapshot,
            allowed_origins=task.allowed_origins,
        )

    def _run_action(
        self,
        task: BrowserTask,
        action: BrowserAction,
    ):
        executor = BrowserAgent(self._transport)
        return executor.execute_action(task, action)

    def _assert_current_origin(self, task: BrowserTask) -> None:
        current = self._transport.current_url().stdout.strip()
        if not current or not task.origin_allowed(current):
            raise BrowserGoalAgentError(
                "browser navigated outside the task's allowed origins"
            )

    @staticmethod
    def _prepare_directories(task: BrowserTask) -> None:
        profile = task.profile_dir.expanduser().resolve()
        workspace = task.workspace_dir.expanduser().resolve()
        for path, label in ((profile, "profile"), (workspace, "workspace")):
            if path.exists() and path.is_symlink():
                raise BrowserGoalAgentError(
                    f"{label} directory must not be a symlink"
                )
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise BrowserGoalAgentError(
                    f"{label} directory could not be prepared"
                ) from exc


def _verify(
    observation: BrowserObservation,
    verification: BrowserVerification,
) -> tuple[bool, tuple[str, ...]]:
    verification.validate()
    snapshot_lower = observation.snapshot.lower()
    url_lower = observation.url.lower()
    matched: list[str] = []

    for expected in verification.text:
        if expected.lower() not in snapshot_lower:
            return False, tuple(matched)
        matched.append(f"text:{expected}")

    for expected in verification.url_contains:
        if expected.lower() not in url_lower:
            return False, tuple(matched)
        matched.append(f"url:{expected}")

    # A completion plan without explicit evidence is not accepted.
    return bool(matched), tuple(matched)


def _goal_requires_confirmation(goal: str) -> bool:
    normalized = " ".join(re.findall(r"[a-z0-9]+", goal.lower()))
    risky_single_words = {
        "submit",
        "send",
        "delete",
        "remove",
        "purchase",
        "pay",
        "payment",
        "book",
        "apply",
        "publish",
        "post",
        "transfer",
        "cancel",
        "unsubscribe",
        "order",
    }
    if any(re.search(rf"\\b{re.escape(word)}\\b", normalized) for word in risky_single_words):
        return True

    # "confirm" is ambiguous: asking the agent to confirm observed state is safe,
    # while confirming an external transaction/submission is consequential.
    return bool(
        re.search(
            r"\\bconfirm(?:ation)?\\s+(?:the\\s+)?"
            r"(?:purchase|payment|booking|order|transfer|submission|application|send|delete|cancellation)",
            normalized,
        )
    )


def _safe_history_line(action: BrowserAction, output: str) -> str:
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:12]
    target = action.target or action.url or action.kind
    return f"{action.kind} target={target!r} output_sha256={digest}"


def _fingerprint(url: str, snapshot: str) -> str:
    return hashlib.sha256(
        (url + "\n" + snapshot).encode("utf-8", errors="replace")
    ).hexdigest()
