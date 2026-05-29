"""Operations menu panel renderer for the POCS TUI."""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from panoptes.pocs.tui.layout import Layout
    from panoptes.pocs.tui.model import POCSModel

MENU_ITEMS: list[tuple[str, str | None]] = [
    ("Start nightly run", "action_start_run"),
    ("Stop run", "action_stop_run"),
    ("Park telescope", "action_park"),
    ("─── Procedures ───────────────────────", None),
    ("Polar alignment", "action_polar_align"),
    ("Focus run", "action_focus_run"),
    ("Take dark frames", "action_take_darks"),
    ("─── Hardware ──────────────────────────", None),
    ("Initialize POCS", "action_initialize"),
    ("Abort exposure", "action_abort_exposure"),
    ("─── Session ───────────────────────────", None),
    ("Reload config", "action_reload_config"),
    ("Shutdown POCS", "action_power_down"),
    ("Quit TUI", "action_quit"),
]

SELECTABLE: list[int] = [i for i, (_, action) in enumerate(MENU_ITEMS) if action is not None]


def get_menu_action(cursor: int) -> str | None:
    """Return the action name for the current cursor position.

    Args:
        cursor: Current menu index.

    Returns:
        Action name for the current item, if any.
    """
    if 0 <= cursor < len(MENU_ITEMS):
        return MENU_ITEMS[cursor][1]
    return None


def menu_next(cursor: int) -> int:
    """Move the cursor to the next selectable item.

    Args:
        cursor: Current menu index.

    Returns:
        Updated cursor position.
    """
    for idx in SELECTABLE:
        if idx > cursor:
            return idx
    return cursor


def menu_prev(cursor: int) -> int:
    """Move the cursor to the previous selectable item.

    Args:
        cursor: Current menu index.

    Returns:
        Updated cursor position.
    """
    for idx in reversed(SELECTABLE):
        if idx < cursor:
            return idx
    return cursor


def render_operations(
    stdscr: Any,
    layout: Layout,
    model: POCSModel,
    menu_cursor: int,
    cmdlog: Any,
) -> None:
    """Render the operations menu.

    Args:
        stdscr: Curses screen.
        layout: Computed screen layout.
        model: Current UI model.
        menu_cursor: Selected menu index.
        cmdlog: Command log renderer source.
    """
    del model
    from panoptes.pocs.tui.panels.dashboard import _safe_addstr, render_cmdlog_panel

    r = layout.main
    _safe_addstr(stdscr, r.y, r.x + 2, " OPERATIONS ", curses.A_BOLD)

    for i, (label, action) in enumerate(MENU_ITEMS):
        row = r.y + 1 + i
        if row >= r.y + r.h - 1:
            break

        is_separator = action is None
        is_selected = i == menu_cursor and not is_separator

        if is_separator:
            _safe_addstr(stdscr, row, r.x + 2, label, curses.A_DIM)
        elif is_selected:
            _safe_addstr(stdscr, row, r.x + 2, f"▶ {label}", curses.A_BOLD | curses.A_REVERSE)
        else:
            _safe_addstr(stdscr, row, r.x + 4, label)

    render_cmdlog_panel(stdscr, layout, cmdlog)
