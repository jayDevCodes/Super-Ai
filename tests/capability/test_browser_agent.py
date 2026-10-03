from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from capabilities.browser.agent import (
    BROWSER_CAPABILITY_SPEC,
    BrowserAction,
    BrowserAgent,
    BrowserAgentError,
    BrowserTask,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._current_url = "https://example.com"

    def open(self, url, **kwargs):
        self.calls.append(("open", url))
        self._current_url = url
        return FakeResult("opened")

    def current_url(self):
        self.calls.append(("current_url",))
        return FakeResult(self._current_url)

    def goto(self, url):
        self.calls.append(("goto", url))
        self._current_url = url
        return FakeResult("goto")

    def snapshot(self):
        self.calls.append(("snapshot",))
        return FakeResult("snapshot")

    def find_text(self, value):
        self.calls.append(("find", value))
        return FakeResult("find")

    def click(self, target):
        self.calls.append(("click", target))
        return FakeResult("click")

    def fill(self, target, value):
        self.calls.append(("fill", target, value))
        return FakeResult("fill")

    def type(self, value):
        self.calls.append(("type", value))
        return FakeResult("type")

    def select(self, target, value):
        self.calls.append(("select", target, value))
        return FakeResult("select")

    def check(self, target):
        self.calls.append(("check", target))
        return FakeResult("check")

    def uncheck(self, target):
        self.calls.append(("uncheck", target))
        return FakeResult("uncheck")

    def press(self, key):
        self.calls.append(("press", key))
        return FakeResult("press")

    def scroll(self, direction, amount):
        self.calls.append(("scroll", direction, str(amount)))
        return FakeResult("scroll")

    def wait(self, seconds):
        self.calls.append(("wait", str(seconds)))
        return FakeResult("wait")

    def screenshot(self, path):
        self.calls.append(("screenshot", str(path)))
        return FakeResult("screenshot")

    def eval(self, expression):
        self.calls.append(("eval", expression))
        return FakeResult("extract")

    def close(self):
        self.calls.append(("close",))
        return FakeResult("close")


class FakeResult:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


class BrowserAgentTests(unittest.TestCase):
    def test_capability_contract_is_valid(self) -> None:
        BROWSER_CAPABILITY_SPEC.validate()

    def test_start_origin_must_be_allowlisted(self) -> None:
        task = BrowserTask(
            goal="Open a page",
            start_url="https://example.com",
            allowed_origins=("https://google.com",),
        )
        with self.assertRaises(ValueError):
            task.validate()

    def test_fill_requires_value(self) -> None:
        with self.assertRaises(ValueError):
            BrowserAction(kind="fill", target="@e1").validate()

    def test_select_requires_value(self) -> None:
        with self.assertRaises(ValueError):
            BrowserAction(kind="select", target="@e1").validate()

    def test_redirect_to_unallowlisted_origin_is_rejected(self) -> None:
        transport = FakeTransport()
        agent = BrowserAgent(transport)
        task = BrowserTask(
            goal="Follow only approved pages",
            start_url="https://example.com",
            allowed_origins=("https://example.com",),
            actions=(BrowserAction(kind="goto", url="https://example.com/next"),),
        )
        transport._current_url = "https://example.com"
        original_goto = transport.goto

        def redirecting_goto(url):
            result = original_goto(url)
            transport._current_url = "https://accounts.evil.example"
            return result

        transport.goto = redirecting_goto
        with self.assertRaises(BrowserAgentError):
            agent.execute(task)

    def test_embedded_credentials_are_rejected(self) -> None:
        task = BrowserTask(
            goal="Open a page",
            start_url="https://user:pass@example.com",
            allowed_origins=("https://example.com",),
        )
        with self.assertRaises(ValueError):
            task.validate()

    def test_external_navigation_is_rejected(self) -> None:
        transport = FakeTransport()
        agent = BrowserAgent(transport)
        task = BrowserTask(
            goal="Stay on the approved site",
            start_url="https://example.com",
            allowed_origins=("https://example.com",),
            actions=(BrowserAction(kind="goto", url="https://evil.example"),),
        )
        with self.assertRaises(BrowserAgentError):
            agent.execute(task)

    def test_consequential_action_requires_confirmation(self) -> None:
        transport = FakeTransport()
        agent = BrowserAgent(transport)
        task = BrowserTask(
            goal="Submit a form",
            start_url="https://example.com",
            allowed_origins=("https://example.com",),
            actions=(BrowserAction(kind="click", target="@e7", consequential=True),),
            confirmed=False,
        )
        with self.assertRaises(BrowserAgentError):
            agent.execute(task)

    def test_non_consequential_action_executes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = FakeTransport()
            agent = BrowserAgent(transport)
            task = BrowserTask(
                goal="Inspect the page",
                start_url="https://example.com",
                allowed_origins=("https://example.com",),
                profile_dir=root / "profile",
                workspace_dir=root / "workspace",
                actions=(
                    BrowserAction(kind="snapshot"),
                    BrowserAction(kind="find_text", target="Sign in"),
                    BrowserAction(kind="extract_text"),
                ),
            )
            result = agent.execute(task)
            self.assertTrue(result.success)
            self.assertEqual(result.steps_completed, 3)
            self.assertEqual(
                [call[0] for call in transport.calls],
                ["open", "current_url", "snapshot", "current_url", "find", "current_url", "eval", "current_url"],
            )

    def test_screenshot_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = FakeTransport()
            agent = BrowserAgent(transport)
            task = BrowserTask(
                goal="Capture proof",
                start_url="https://example.com",
                allowed_origins=("https://example.com",),
                profile_dir=root / "profile",
                workspace_dir=root / "workspace",
                actions=(
                    BrowserAction(kind="screenshot", path="../../secret.png"),
                ),
            )
            with self.assertRaises(BrowserAgentError):
                agent.execute(task)


if __name__ == "__main__":
    unittest.main()
