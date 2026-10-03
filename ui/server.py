#!/usr/bin/env python3
"""Local, dependency-free dashboard for Super-Ai."""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capabilities.browser.agent import BrowserAction, BrowserAgent, BrowserTask
from capabilities.browser.cli import PlaywrightCliTransport
from core.models import TaskModelManager


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "ui"), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._json({"ok": True, "service": "Super-Ai dashboard"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path not in {"/api/run-browser-demo", "/api/run-browser-task"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = self._request_json()
        if payload is None:
            return
        goal = "Inspect the public Example Domain page without making changes."
        start_url = "https://example.com/"
        if self.path == "/api/run-browser-task":
            goal = str(payload.get("goal", "")).strip()
            start_url = str(payload.get("start_url", "")).strip()
            if not goal or len(goal) > 1_000:
                self._json({"ok": False, "message": "Enter a task between 1 and 1,000 characters."}, status=400)
                return
            if not start_url:
                self._json({"ok": False, "message": "Enter an HTTPS target URL."}, status=400)
                return
        try:
            allowed_origin = _origin_for(start_url)
        except ValueError as exc:
            self._json({"ok": False, "message": str(exc)}, status=400)
            return

        transport = PlaywrightCliTransport(session="super-ai-dashboard-demo")
        task = BrowserTask(
            goal=goal,
            start_url=start_url,
            allowed_origins=(allowed_origin,),
            profile_dir=ROOT / ".super-ai/browser/profile",
            workspace_dir=ROOT / ".super-ai/browser/workspace",
            headed=False,
            actions=(
                BrowserAction(kind="snapshot"),
                BrowserAction(kind="extract_text"),
            ),
        )
        try:
            result = BrowserAgent(transport).execute(task)
            model_selection = TaskModelManager().select(
                goal,
                max_ram_mb=1_600,
                max_disk_mb=1_200,
            )
            self._json({
                "ok": result.success,
                "steps": result.steps_completed,
                "message": "Read-only browser inspection completed successfully.",
                "model": model_selection.model,
                "model_reason": model_selection.reason,
            })
        except Exception as exc:
            self._json({"ok": False, "message": f"{type(exc).__name__}: {exc}"}, status=500)
        finally:
            try:
                transport.close()
            except Exception:
                pass

    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _request_json(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4_096:
                raise ValueError("request is too large")
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("request must be an object")
            return value
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "message": f"Invalid task request: {exc}"}, status=400)
            return None


def _origin_for(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("target URL must be a credential-free HTTPS address")
    return f"https://{parsed.netloc}"


if __name__ == "__main__":
    host, port = "127.0.0.1", 8787
    print(f"Super-Ai dashboard: http://{host}:{port}")
    ThreadingHTTPServer((host, port), DashboardHandler).serve_forever()
