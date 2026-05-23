"""Keyboard input mapping and dispatch shims for the TUI skeleton."""

from __future__ import annotations

import curses
from typing import Any

KEY_MAP: dict[int, str] = {
    ord("q"): "quit",
    ord("p"): "park",
    ord("a"): "abort_exposure",
    ord(" "): "pause",
    ord("/"): "filter",
    ord("?"): "help",
    curses.KEY_F1: "view_dashboard",
    curses.KEY_F2: "view_hardware",
    curses.KEY_F3: "view_scheduler",
    curses.KEY_F4: "view_safety",
    curses.KEY_F5: "view_help",
    curses.KEY_UP: "up",
    curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    10: "enter",
    13: "enter",
    27: "escape",
}


def dispatch(action: str, handlers: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    """Dispatch an action name to an optional handler table.

    TODO: Expand this dispatcher to support modal input and richer focus-aware routing.
    """
    if not handlers:
        return None
    handler = handlers.get(action)
    if handler is None:
        return None
    return handler(**kwargs)
