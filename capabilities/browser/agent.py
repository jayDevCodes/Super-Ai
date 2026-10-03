from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import urlparse

from core.contracts import CapabilitySpec, ResourceContract

from .cli import PlaywrightCliResult, PlaywrightCliTransport


BrowserActionKind = Literal[
    "goto",
    "snapshot",
    "find_text",
    "click",
    "fill",
    "type",
    "select",
    "check",
    "uncheck",
    "press",
    "scroll",
    "wait",
    "screenshot",
    "extract_text",
]


@dataclass(frozen=True, slots=True)
class BrowserAction:
    """One deterministic browser operation requested by the planner."""

    kind: BrowserActionKind
    target: str | None = None
    value: str | None = None
    url: str | None = None
    amount: int | None = None
    path: str | None = None
    consequential: bool = False

    def validate(self) -> None:
        if self.kind == "goto":
            if not self.url:
                raise ValueError("goto action requires url")
        elif self.kind in {"click", "check", "uncheck"}:
            if not self.target:
                raise ValueError(f"{self.kind} action requires target")
        elif self.kind == "fill":
            if not self.target:
                raise ValueError("fill action requires target")
            if self.value is None:
                raise ValueError("fill action requires value")
        elif self.kind == "select":
            if not self.target:
                raise ValueError("select action requires target")
            if self.value is None:
                raise ValueError("select action requires value")
        elif self.kind == "find_text":
            if not self.target:
                raise ValueError("find_text action requires target text")
        elif self.kind == "type" and self.value is None:
            raise ValueError("type action requires value")
        elif self.kind == "press" and not self.value:
            raise ValueError("press action requires key in value")
        elif self.kind == "scroll":
            if self.value not in {"up", "down", "left", "right"}:
                raise ValueError("scroll value must be up/down/left/right")
            if self.amount is None or self.amount <= 0:
                raise ValueError("scroll action requires a positive amount")
        elif self.kind == "wait":
            if self.amount is None or self.amount <= 0:
                raise ValueError("wait action requires a positive amount")
        elif self.kind == "screenshot" and not self.path:
            raise ValueError("screenshot action requires path")

        if self.url is not None and len(self.url) > 2048:
            raise ValueError("url is too long")
        if self.path is not None and "\x00" in self.path:
            raise ValueError("path contains a NUL byte")



@dataclass(frozen=True, slots=True)
class BrowserTask:
    """User-authorized browser task with an explicit origin boundary."""

    goal: str
    start_url: str
    actions: tuple[BrowserAction, ...] = field(default_factory=tuple)
    allowed_origins: tuple[str, ...] = field(default_factory=tuple)
    session: str = "super-ai-browser"
    profile_dir: Path = Path(".super-ai/browser/profile")
    workspace_dir: Path = Path(".super-ai/browser/workspace")
    headed: bool = True
    confirmed: bool = False

    def validate(self) -> None:
        if not self.goal or not self.goal.strip():
            raise ValueError("goal must be non-empty")
        _validate_https_origin_url(self.start_url)

        if not self.allowed_origins:
            raise ValueError("allowed_origins must explicitly allow the target origin")

        normalized_origins = tuple(_normalize_origin(value) for value in self.allowed_origins)
        if _normalize_origin(self.start_url) not in normalized_origins:
            raise ValueError("start_url origin is not in allowed_origins")

        if not self.session or self.session.strip() != self.session:
            raise ValueError("session must be a non-empty trimmed string")
        if len(self.session) > 64:
            raise ValueError("session is too long")

        if not str(self.profile_dir).strip() or not str(self.workspace_dir).strip():
            raise ValueError("profile_dir and workspace_dir must be provided")

        for action in self.actions:
            action.validate()

    def origin_allowed(self, url: str) -> bool:
        return _normalize_origin(url) in {
            _normalize_origin(value) for value in self.allowed_origins
        }


@dataclass(frozen=True, slots=True)
class BrowserResult:
    """Bounded execution evidence. Action input values are intentionally omitted."""

    goal: str
    success: bool
    steps_completed: int
    last_output: str
    action_results: tuple[str, ...]
    screenshot_paths: tuple[str, ...]
    error: str | None = None


class BrowserAgentError(RuntimeError):
    """Raised when a browser task violates policy or cannot execute."""


BROWSER_CAPABILITY_SPEC = CapabilitySpec(
    capability_id="browser.agent",
    version="1.0.0",
    description=(
        "Controlled Chrome webpage navigation and interaction using a user-approved "
        "persistent browser profile."
    ),
    resource=ResourceContract(
        ram_soft_mb=256,
        ram_hard_mb=1024,
        disk_mb=512,
        cpu_threads=2,
        max_concurrency=1,
    ),
    permissions=frozenset({"browser", "network"}),
    verification_required=True,
)


class BrowserAgent:
    """Execute deterministic browser actions while an AI planner supplies intent."""

    spec = BROWSER_CAPABILITY_SPEC

    def __init__(self, transport: PlaywrightCliTransport) -> None:
        self._transport = transport

    def execute(
        self,
        task: BrowserTask | Mapping[str, Any],
    ) -> BrowserResult:
        normalized = _coerce_task(task)
        normalized.validate()

        profile = normalized.profile_dir.expanduser().resolve()
        workspace = normalized.workspace_dir.expanduser().resolve()
        profile.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)

        outputs: list[str] = []
        screenshots: list[str] = []

        try:
            opened = self._transport.open(
                normalized.start_url,
                persistent=True,
                profile=profile,
                headed=normalized.headed,
                browser="chrome",
            )
            outputs.append(opened.stdout)

            for index, action in enumerate(normalized.actions, start=1):
                if action.consequential and not normalized.confirmed:
                    raise BrowserAgentError(
                        f"action {index} is consequential and requires confirmation"
                    )

                result = self._run_action(action, normalized, workspace)
                outputs.append(result.stdout)

                if action.kind == "screenshot" and action.path:
                    screenshot_path = _safe_workspace_path(workspace, action.path)
                    screenshots.append(str(screenshot_path))

            return BrowserResult(
                goal=normalized.goal,
                success=True,
                steps_completed=len(normalized.actions),
                last_output=outputs[-1] if outputs else "",
                action_results=tuple(_summarize(value) for value in outputs),
                screenshot_paths=tuple(screenshots),
            )
        except BrowserAgentError:
            raise
        except Exception as exc:
            raise BrowserAgentError(
                f"browser task failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _run_action(
        self,
        action: BrowserAction,
        task: BrowserTask,
        workspace: Path,
    ) -> PlaywrightCliResult:
        if action.kind == "goto":
            assert action.url is not None
            _validate_https_origin_url(action.url)
            if not task.origin_allowed(action.url):
                raise BrowserAgentError(
                    f"navigation origin is not allowlisted: {_normalize_origin(action.url)}"
                )
            return self._transport.goto(action.url)

        if action.kind == "snapshot":
            return self._transport.snapshot()

        if action.kind == "find_text":
            assert action.target is not None
            return self._transport.find_text(action.target)

        if action.kind == "click":
            assert action.target is not None
            return self._transport.click(action.target)

        if action.kind == "fill":
            assert action.target is not None and action.value is not None
            return self._transport.fill(action.target, action.value)

        if action.kind == "type":
            assert action.value is not None
            return self._transport.type(action.value)

        if action.kind == "select":
            assert action.target is not None and action.value is not None
            return self._transport.select(action.target, action.value)

        if action.kind == "check":
            assert action.target is not None
            return self._transport.check(action.target)

        if action.kind == "uncheck":
            assert action.target is not None
            return self._transport.uncheck(action.target)

        if action.kind == "press":
            assert action.value is not None
            return self._transport.press(action.value)

        if action.kind == "scroll":
            assert action.value is not None and action.amount is not None
            return self._transport.scroll(action.value, action.amount)

        if action.kind == "wait":
            assert action.amount is not None
            return self._transport.wait(action.amount)

        if action.kind == "screenshot":
            assert action.path is not None
            target = _safe_workspace_path(workspace, action.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            return self._transport.screenshot(target)

        if action.kind == "extract_text":
            return self._transport.eval(
                "() => document.body ? document.body.innerText : \"\""
            )

        raise BrowserAgentError(f"unsupported browser action: {action.kind}")


def _coerce_task(task: BrowserTask | Mapping[str, Any]) -> BrowserTask:
    if isinstance(task, BrowserTask):
        return task
    if not isinstance(task, Mapping):
        raise TypeError("task must be BrowserTask or mapping")

    raw_actions = task.get("actions", ())
    if not isinstance(raw_actions, (list, tuple)):
        raise TypeError("actions must be a list")

    actions = tuple(
        item if isinstance(item, BrowserAction) else BrowserAction(**item)
        for item in raw_actions
    )

    return BrowserTask(
        goal=str(task["goal"]),
        start_url=str(task["start_url"]),
        actions=actions,
        allowed_origins=tuple(str(item) for item in task["allowed_origins"]),
        session=str(task.get("session", "super-ai-browser")),
        profile_dir=Path(task.get("profile_dir", ".super-ai/browser/profile")),
        workspace_dir=Path(task.get("workspace_dir", ".super-ai/browser/workspace")),
        headed=bool(task.get("headed", True)),
        confirmed=bool(task.get("confirmed", False)),
    )


def _normalize_origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("browser URLs must use https and include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("browser URLs must not contain embedded credentials")
    port = parsed.port
    host = parsed.hostname.lower()
    if port is None:
        return f"https://{host}"
    return f"https://{host}:{port}"


def _validate_https_origin_url(url: str) -> None:
    _normalize_origin(url)


def _safe_workspace_path(workspace: Path, requested: str) -> Path:
    candidate = (workspace / requested).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise BrowserAgentError("screenshot path escapes browser workspace") from exc
    return candidate


def _summarize(value: str, limit: int = 1200) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[step output truncated]"
