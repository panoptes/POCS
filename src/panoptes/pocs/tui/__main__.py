"""Entry point and render loop for the POCS terminal UI."""

from __future__ import annotations

import curses
from time import sleep
from typing import Any

from panoptes.pocs.tui.actions import dispatch as action_dispatch
from panoptes.pocs.tui.bridge import Bridge
from panoptes.pocs.tui.cmdlog import CmdLog
from panoptes.pocs.tui.input import handle as input_handle
from panoptes.pocs.tui.layout import Layout, View, layout_compute
from panoptes.pocs.tui.model import POCSModel
from panoptes.pocs.tui.panels.dashboard import (
    render_cmdlog_panel,
    render_dashboard,
    render_modal,
    render_nav_bar,
    render_status_bar,
    render_tab_bar,
)
from panoptes.pocs.tui.panels.help import render_help
from panoptes.pocs.tui.panels.operations import (
    SELECTABLE,
    get_menu_action,
    menu_next,
    menu_prev,
    render_operations,
)
from panoptes.pocs.tui.scanner import Scanner
from panoptes.pocs.tui.theme import init_colors

FPS = 20
_FRAME_S = 1.0 / FPS

_VIEW_CYCLE = [View.DASHBOARD, View.HARDWARE, View.SCHEDULER, View.OPERATIONS, View.CONFIG, View.HELP]


def _next_view(current: View) -> View:
    """Return the next view in the tab cycle.

    Args:
        current: Current active view.

    Returns:
        Next view.
    """
    idx = _VIEW_CYCLE.index(current) if current in _VIEW_CYCLE else 0
    return _VIEW_CYCLE[(idx + 1) % len(_VIEW_CYCLE)]


def _prev_view(current: View) -> View:
    """Return the previous view in the tab cycle.

    Args:
        current: Current active view.

    Returns:
        Previous view.
    """
    idx = _VIEW_CYCLE.index(current) if current in _VIEW_CYCLE else 0
    return _VIEW_CYCLE[(idx - 1) % len(_VIEW_CYCLE)]


def _handle_modal_nav(nav: str, model: POCSModel, bridge: Bridge, cmdlog: CmdLog) -> None:
    """Handle navigation when a modal dialog is active.

    Args:
        nav: Navigation action name.
        model: Current UI model.
        bridge: Action bridge.
        cmdlog: Command log sink.
    """
    modal = model.modal
    if nav in ("up", "left"):
        modal.selected = max(0, modal.selected - 1)
    elif nav in ("down", "right"):
        modal.selected = min(len(modal.choices) - 1, modal.selected + 1)
    elif nav == "enter":
        callback = modal.callback
        modal.active = False
        modal.callback = ""
        if modal.selected == 0 and callback:
            action_dispatch(callback, bridge, cmdlog, model)
    elif nav == "escape":
        modal.active = False
        modal.callback = ""


def main(stdscr: Any, pocs: Any = None) -> None:
    """Run the curses render loop.

    Args:
        stdscr: Curses screen.
        pocs: Optional in-process POCS instance.
    """
    curses.curs_set(0)
    stdscr.nodelay(True)
    init_colors(stdscr)

    bridge = Bridge(pocs=pocs)
    scanner = Scanner(pocs=pocs, interval_s=0.5)
    layout = Layout()
    cmdlog = CmdLog()
    model = POCSModel()
    menu_cursor = SELECTABLE[0] if SELECTABLE else 0

    scanner.start()

    try:
        while True:
            key = stdscr.getch()
            nav = input_handle(key) if key != -1 else None

            if nav is not None:
                if model.modal.active:
                    _handle_modal_nav(nav, model, bridge, cmdlog)
                elif nav == "quit":
                    action_dispatch("action_quit", bridge, cmdlog, model)
                elif nav == "tab":
                    layout.active_view = _next_view(layout.active_view)
                elif nav == "left" and layout.active_view != View.DASHBOARD:
                    layout.active_view = _prev_view(layout.active_view)
                elif nav == "right" and layout.active_view != View.HELP:
                    layout.active_view = _next_view(layout.active_view)
                elif nav.startswith("view_"):
                    view_name = nav[5:].upper()
                    try:
                        layout.active_view = View[view_name]
                    except KeyError:
                        pass
                elif layout.active_view == View.OPERATIONS:
                    if nav == "up":
                        menu_cursor = menu_prev(menu_cursor)
                    elif nav == "down":
                        menu_cursor = menu_next(menu_cursor)
                    elif nav == "enter":
                        action_name = get_menu_action(menu_cursor)
                        if action_name:
                            action_dispatch(action_name, bridge, cmdlog, model)
                            scanner.force_update()

            if model.system.state == "__quit__":
                break

            fresh = scanner.snapshot()
            fresh.modal = model.modal
            fresh.config_editor = model.config_editor
            model = fresh

            height, width = stdscr.getmaxyx()
            layout.width = width
            layout.height = height
            layout_compute(layout)

            stdscr.erase()
            render_tab_bar(stdscr, layout, model)
            render_status_bar(stdscr, layout, model)
            render_nav_bar(stdscr, layout)

            if layout.active_view == View.DASHBOARD:
                render_dashboard(stdscr, layout, model, cmdlog)
            elif layout.active_view == View.OPERATIONS:
                render_operations(stdscr, layout, model, menu_cursor, cmdlog)
            elif layout.active_view == View.HELP:
                render_help(stdscr, layout, model)
            else:
                from panoptes.pocs.tui.panels.dashboard import _safe_addstr

                _safe_addstr(
                    stdscr,
                    layout.main.y + 1,
                    layout.main.x + 2,
                    f"{layout.active_view.name} view — coming soon",
                )
                render_cmdlog_panel(stdscr, layout, cmdlog)

            if model.modal.active:
                render_modal(stdscr, layout, model)

            stdscr.refresh()
            sleep(_FRAME_S)

    finally:
        scanner.stop()
        bridge.shutdown()


def curses_main(pocs: Any = None) -> None:
    """Launch the curses application.

    Loguru's stderr sink is removed before entering curses to prevent log
    lines from corrupting the terminal display.  A minimal error-only sink is
    restored on exit so the caller still sees critical messages.

    Args:
        pocs: Optional in-process POCS instance.
    """
    import sys

    from loguru import logger

    logger.remove()  # silence all sinks while curses owns the terminal
    try:
        curses.wrapper(lambda stdscr: main(stdscr, pocs=pocs))
    finally:
        logger.add(sys.stderr, level="ERROR")


if __name__ == "__main__":
    curses_main()
