"""Help panel renderer for the POCS TUI."""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from panoptes.pocs.tui.layout import Layout
    from panoptes.pocs.tui.model import POCSModel

_HELP_LINES = [
    ("Navigation", None),
    ("  Tab / F1-F6", "Switch between views"),
    ("  ↑ / ↓", "Move selection within a menu or list"),
    ("  ← / →", "Navigate nested menus or previous tab"),
    ("  Enter", "Activate selected item / confirm edit"),
    ("  Esc", "Go back one level / cancel / dismiss modal"),
    ("  q", "Quit (shows confirmation)"),
    ("", None),
    ("Views", None),
    ("  Dashboard", "Live observatory status overview"),
    ("  Hardware", "Mount, camera, focuser, dome detail"),
    ("  Scheduler", "Candidate targets and active observation"),
    ("  Operations", "Control: start/stop run, procedures, hardware"),
    ("  Config", "Browse and edit configuration keys"),
    ("", None),
    ("Operations menu", None),
    ("  All actions are in the Operations view.", None),
    ("  Destructive actions show a confirmation dialog.", None),
]


def render_help(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render the help view.

    Args:
        stdscr: Curses screen.
        layout: Computed screen layout.
        model: Current UI model.
    """
    del model
    from panoptes.pocs.tui.panels.dashboard import _safe_addstr

    r = layout.main
    _safe_addstr(stdscr, r.y, r.x + 2, " HELP ", curses.A_BOLD)

    row = r.y + 2
    for label, desc in _HELP_LINES:
        if row >= r.y + r.h:
            break
        if desc is None:
            attr = curses.A_BOLD if label else curses.A_NORMAL
            _safe_addstr(stdscr, row, r.x + 2, label, attr)
        else:
            _safe_addstr(stdscr, row, r.x + 2, label, curses.A_DIM)
            _safe_addstr(stdscr, row, r.x + 20, desc)
        row += 1
