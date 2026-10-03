from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Sequence


class PlaywrightCliError(RuntimeError):
    """Raised when the Playwright CLI cannot execute a browser operation."""


@dataclass(frozen=True, slots=True)
class PlaywrightCliResult:
    """Bounded result returned by one Playwright CLI invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class PlaywrightCliTransport:
    """Small subprocess adapter around the official Playwright CLI.

    The adapter never uses a shell. Browser arguments are passed as argv so
    page text cannot become shell syntax. Session/profile state is supplied
    explicitly by the browser capability rather than through credentials.
    """

    def __init__(
        self,
        *,
        executable: str | None = None,
        session: str = "super-ai-browser",
        timeout_seconds: float = 45.0,
        output_dir: Path | None = None,
    ) -> None:
        self.executable = (
            executable
            or os.getenv("SUPER_AI_PLAYWRIGHT_CLI")
            or "playwright-cli"
        )
        if not self.executable or self.executable.strip() != self.executable:
            raise ValueError("Playwright CLI executable must be a trimmed string")
        if not session or session.strip() != session:
            raise ValueError("session must be a non-empty trimmed string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.session = session
        self.timeout_seconds = float(timeout_seconds)
        self.output_dir = (
            Path(output_dir).expanduser().resolve()
            if output_dir is not None
            else None
        )

    def run(
        self,
        *args: str,
        check: bool = True,
        timeout_seconds: float | None = None,
    ) -> PlaywrightCliResult:
        if any(not isinstance(arg, str) or not arg for arg in args):
            raise ValueError("CLI arguments must be non-empty strings")

        command = [
            self.executable,
            f"-s={self.session}",
            *args,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds or self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise PlaywrightCliError(
                "Playwright CLI was not found. Install @playwright/cli or set "
                "SUPER_AI_PLAYWRIGHT_CLI."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise PlaywrightCliError("Playwright CLI command timed out") from exc
        except OSError as exc:
            raise PlaywrightCliError("failed to start Playwright CLI") from exc

        result = PlaywrightCliResult(
            args=tuple(args),
            returncode=completed.returncode,
            stdout=_bound(completed.stdout),
            stderr=_bound(completed.stderr),
        )
        if check and not result.ok:
            detail = result.stderr or result.stdout or "unknown Playwright CLI failure"
            raise PlaywrightCliError(
                f"Playwright CLI exited with {result.returncode}: {detail}"
            )
        return result

    def open(
        self,
        url: str,
        *,
        persistent: bool = True,
        profile: Path | None = None,
        headed: bool = True,
        browser: str = "chrome",
    ) -> PlaywrightCliResult:
        args = ["open", url, f"--browser={browser}"]
        if persistent:
            args.append("--persistent")
        if profile is not None:
            args.append(f"--profile={Path(profile).expanduser().resolve()}")
        if headed:
            args.append("--headed")
        return self.run(*args)

    def snapshot(self) -> PlaywrightCliResult:
        return self.run("snapshot")

    def close(self) -> PlaywrightCliResult:
        return self.run("close")

    def state_save(self, filename: Path) -> PlaywrightCliResult:
        return self.run("state-save", str(Path(filename).expanduser().resolve()))

    def state_load(self, filename: Path) -> PlaywrightCliResult:
        return self.run("state-load", str(Path(filename).expanduser().resolve()))

    def _mutate(self, command: str, *args: str) -> PlaywrightCliResult:
        return self.run(command, *args)

    def goto(self, url: str) -> PlaywrightCliResult:
        return self._mutate("goto", url)

    def click(self, target: str) -> PlaywrightCliResult:
        return self._mutate("click", target)

    def fill(self, target: str, value: str) -> PlaywrightCliResult:
        return self._mutate("fill", target, value)

    def type(self, value: str) -> PlaywrightCliResult:
        return self._mutate("type", value)

    def select(self, target: str, value: str) -> PlaywrightCliResult:
        return self._mutate("select", target, value)

    def check(self, target: str) -> PlaywrightCliResult:
        return self._mutate("check", target)

    def uncheck(self, target: str) -> PlaywrightCliResult:
        return self._mutate("uncheck", target)

    def press(self, key: str) -> PlaywrightCliResult:
        return self._mutate("press", key)

    def scroll(self, direction: str, amount: int) -> PlaywrightCliResult:
        if direction not in {"up", "down", "left", "right"}:
            raise ValueError("scroll direction must be up/down/left/right")
        if amount <= 0:
            raise ValueError("scroll amount must be > 0")
        dx = amount if direction == "right" else -amount if direction == "left" else 0
        dy = amount if direction == "down" else -amount if direction == "up" else 0
        return self._mutate("mousewheel", str(dx), str(dy))

    def find_text(self, text: str) -> PlaywrightCliResult:
        return self._mutate("find", text)

    def wait(self, seconds: float) -> PlaywrightCliResult:
        if seconds <= 0:
            raise ValueError("wait seconds must be > 0")
        return self._mutate("wait", str(int(seconds * 1000)))

    def screenshot(self, path: Path | None = None) -> PlaywrightCliResult:
        if path is None:
            return self._mutate("screenshot")
        filename = Path(path).expanduser().resolve()
        return self._mutate("screenshot", f"--filename={filename}")

    def eval(self, expression: str, *, raw: bool = False) -> PlaywrightCliResult:
        if not expression or not expression.strip():
            raise ValueError("eval expression must be non-empty")
        args = ["eval", expression]
        if raw:
            args.append("--raw")
        return self.run(*args)

    def current_url(self) -> PlaywrightCliResult:
        return self.eval("() => location.href", raw=True)


def _bound(value: str, limit: int = 200_000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[output truncated by Super-Ai]"
