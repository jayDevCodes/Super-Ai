from __future__ import annotations

import json
import unittest

from capabilities.browser.agent import BrowserAction
from capabilities.browser.goal_agent import BrowserGoalAgent, BrowserGoalAgentError
from capabilities.browser.planner import (
    BrowserIntentPlanner,
    BrowserObservation,
    BrowserPlan,
    BrowserPlannerError,
    BrowserVerification,
    _plan_from_json,
)


class FakePlanner(BrowserIntentPlanner):
    def __init__(self, plans: list[BrowserPlan]) -> None:
        self.plans = plans

    def plan(self, goal, observation, *, history=()):
        if not self.plans:
            raise BrowserPlannerError("no more plans")
        return self.plans.pop(0)


class GoalTransport:
    def __init__(self) -> None:
        self.current = "https://example.com"
        self.calls: list[tuple[str, ...]] = []

    def open(self, url, **kwargs):
        self.current = url
        self.calls.append(("open", url))
        return Result("opened")

    def current_url(self):
        self.calls.append(("current_url",))
        return Result(self.current)

    def snapshot(self):
        self.calls.append(("snapshot",))
        return Result(
            '- heading "Example" [level=1]\n'
            '- button "Start" [ref=e1]\n'
            '- text: "Done"'
        )

    def click(self, target):
        self.calls.append(("click", target))
        return Result("clicked")

    def fill(self, target, value):
        self.calls.append(("fill", target, value))
        return Result("filled")

    def type(self, value):
        self.calls.append(("type", value))
        return Result("typed")

    def select(self, target, value):
        self.calls.append(("select", target, value))
        return Result("selected")

    def check(self, target):
        self.calls.append(("check", target))
        return Result("checked")

    def uncheck(self, target):
        self.calls.append(("uncheck", target))
        return Result("unchecked")

    def press(self, key):
        self.calls.append(("press", key))
        return Result("pressed")

    def scroll(self, direction, amount):
        self.calls.append(("scroll", direction, str(amount)))
        return Result("scrolled")

    def wait(self, seconds):
        self.calls.append(("wait", str(seconds)))
        return Result("waited")

    def screenshot(self, path):
        self.calls.append(("screenshot", str(path)))
        return Result("screenshot")

    def eval(self, expression, *, raw=False):
        self.calls.append(("eval", expression))
        return Result("Done")

    def find_text(self, text):
        self.calls.append(("find", text))
        return Result("found")


class Result:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


class BrowserPlannerTests(unittest.TestCase):
    def test_structured_json_plan_is_parsed(self):
        raw = {
            "actions": [
                {
                    "kind": "click",
                    "target": "e1",
                    "value": None,
                    "url": None,
                    "amount": None,
                    "path": None,
                    "consequential": False,
                }
            ],
            "done": False,
            "summary": "",
            "verification": {"text": [], "url_contains": []},
            "needs_confirmation": False,
            "confirmation_reason": "",
        }
        plan = _plan_from_json(raw)
        self.assertEqual(plan.actions[0].kind, "click")
        self.assertEqual(plan.actions[0].target, "e1")

    def test_completion_requires_grounded_verification(self):
        transport = GoalTransport()
        planner = FakePlanner(
            [
                BrowserPlan(
                    done=True,
                    summary="Done",
                    verification=BrowserVerification(text=("Done",)),
                )
            ]
        )
        agent = BrowserGoalAgent(
            transport=transport,
            planner=planner,
            max_cycles=2,
        )
        from capabilities.browser.agent import BrowserTask

        result = agent.run(
            BrowserTask(
                goal="Confirm the page is done",
                start_url="https://example.com",
                allowed_origins=("https://example.com",),
            )
        )
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.verification_passed)

    def test_consequential_goal_stops_for_confirmation(self):
        transport = GoalTransport()
        planner = FakePlanner(
            [
                BrowserPlan(
                    actions=(
                        BrowserAction(
                            kind="click",
                            target="e1",
                            consequential=True,
                        ),
                    ),
                    summary="Ready to submit",
                    verification=BrowserVerification(),
                    needs_confirmation=True,
                    confirmation_reason="Final submission changes external state.",
                )
            ]
        )
        agent = BrowserGoalAgent(
            transport=transport,
            planner=planner,
        )
        from capabilities.browser.agent import BrowserTask

        result = agent.run(
            BrowserTask(
                goal="Submit the form",
                start_url="https://example.com",
                allowed_origins=("https://example.com",),
            )
        )
        self.assertEqual(result.status, "confirmation_required")
        self.assertTrue(result.confirmation_required)
        self.assertFalse(any(call[0] == "click" for call in transport.calls))

    def test_goal_with_safe_action_can_complete_next_cycle(self):
        transport = GoalTransport()
        planner = FakePlanner(
            [
                BrowserPlan(
                    actions=(BrowserAction(kind="click", target="e1"),),
                ),
                BrowserPlan(
                    done=True,
                    summary="Completed",
                    verification=BrowserVerification(text=("Done",)),
                ),
            ]
        )
        agent = BrowserGoalAgent(
            transport=transport,
            planner=planner,
            max_cycles=3,
        )
        from capabilities.browser.agent import BrowserTask

        result = agent.run(
            BrowserTask(
                goal="Open the page and finish",
                start_url="https://example.com",
                allowed_origins=("https://example.com",),
            )
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.actions_executed, 1)

    def test_observation_bounds_snapshot(self):
        obs = BrowserObservation(
            url="https://example.com",
            snapshot="x" * 10,
            max_snapshot_chars=5,
        )
        self.assertIn("TRUNCATED", obs.bounded_snapshot)

    def test_plan_rejects_too_many_actions(self):
        plan = BrowserPlan(
            actions=tuple(
                BrowserAction(kind="snapshot") for _ in range(5)
            )
        )
        with self.assertRaises(BrowserPlannerError):
            plan.validate(max_actions=4)


if __name__ == "__main__":
    unittest.main()
