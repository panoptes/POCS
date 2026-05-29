"""Navigation input handling for the POCS TUI.

All interaction is menu-driven. No memorised hotkeys are required.
"""

from __future__ import annotations

import curses

NAV_UP = "up"
NAV_DOWN = "down"
NAV_LEFT = "left"
NAV_RIGHT = "right"
NAV_ENTER = "enter"
NAV_ESCAPE = "escape"
NAV_TAB = "tab"
NAV_QUIT = "quit"

KEY_MAP: dict[int, str] = {
    curses.KEY_UP: NAV_UP,
    curses.KEY_DOWN: NAV_DOWN,
    curses.KEY_LEFT: NAV_LEFT,
    curses.KEY_RIGHT: NAV_RIGHT,
    curses.KEY_BTAB: NAV_LEFT,
    curses.KEY_F1: "view_dashboard",
    curses.KEY_F2: "view_hardware",
    curses.KEY_F3: "view_scheduler",
    curses.KEY_F4: "view_operations",
    curses.KEY_F5: "view_config",
    curses.KEY_F6: "view_help",
    9: NAV_TAB,
    10: NAV_ENTER,
    13: NAV_ENTER,
    27: NAV_ESCAPE,
    ord("q"): NAV_QUIT,
    ord("Q"): NAV_QUIT,
}


def handle(key: int) -> str | None:
    """Map a raw curses key code to a navigation action name.

    Args:
        key: Raw integer key code from ``stdscr.getch()``.

    Returns:
        Action name string, or ``None``.
    """
    return KEY_MAP.get(key)
