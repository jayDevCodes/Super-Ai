"""First-party browser automation capability for Super-Ai."""

from .agent import (
    BrowserAction,
    BrowserAgent,
    BrowserAgentError,
    BrowserResult,
    BrowserTask,
)
from .cli import PlaywrightCliError, PlaywrightCliTransport

__all__ = [
    "BrowserAction",
    "BrowserAgent",
    "BrowserAgentError",
    "BrowserResult",
    "BrowserTask",
    "PlaywrightCliError",
    "PlaywrightCliTransport",
]
