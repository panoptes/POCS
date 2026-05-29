"""Dashboard panel renderers for the POCS TUI."""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from panoptes.pocs.tui.layout import Layout
    from panoptes.pocs.tui.model import POCSModel


def _safe_addstr(stdscr: Any, y: int, x: int, text: str, attr: int = 0) -> None:
    """Draw text clipped to screen bounds without raising.

    Args:
        stdscr: Curses screen.
        y: Row position.
        x: Column position.
        text: Text to draw.
        attr: Optional curses attributes.
    """
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    max_len = max_x - x - 1
    if max_len <= 0:
        return
    try:
        stdscr.addstr(y, x, text[:max_len], attr)
    except curses.error:
        pass


def render_tab_bar(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Draw the tab bar at the top of the screen."""
    del model
    from panoptes.pocs.tui.layout import View

    tabs = [
        (View.DASHBOARD, "Dashboard"),
        (View.HARDWARE, "Hardware"),
        (View.SCHEDULER, "Scheduler"),
        (View.OPERATIONS, "Operations"),
        (View.CONFIG, "Config"),
        (View.HELP, "Help"),
    ]

    y = layout.tab_bar.y
    x = 2
    _safe_addstr(stdscr, y, 0, "POCS ", curses.A_BOLD)

    for view, label in tabs:
        tab_str = f" {label} "
        attr = curses.A_REVERSE if layout.active_view == view else curses.A_NORMAL
        _safe_addstr(stdscr, y, x, tab_str, attr)
        x += len(tab_str) + 1


def render_status_bar(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Draw the state and uptime status bar."""
    state = model.system.state
    uptime = model.system.uptime
    run_indicator = "  ● RUN ACTIVE" if model.system.run_active else ""
    text = f"  state={state}  uptime={uptime}{run_indicator}"
    _safe_addstr(stdscr, layout.status_bar.y, 0, text, curses.A_DIM)


def render_nav_bar(stdscr: Any, layout: Layout) -> None:
    """Draw the bottom navigation hints bar."""
    hints = " Tab=next view  ↑↓=navigate  Enter=select  Esc=back  q=quit"
    _safe_addstr(stdscr, layout.nav_bar.y, 0, hints, curses.A_DIM)


def render_safety_panel(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render the safety summary in ``layout.left_top``."""
    r = layout.left_top
    _safe_addstr(stdscr, r.y, r.x, "─" * r.w)
    _safe_addstr(stdscr, r.y, r.x + 2, " SAFETY ", curses.A_BOLD)

    s = model.safety
    power_str = "OK" if s.ac_power else "NO"
    dark_str = "YES" if s.is_dark else "NO"
    wx_str = "GOOD" if s.good_weather else "BAD"

    power_attr = curses.A_NORMAL if s.ac_power else curses.color_pair(2)
    dark_attr = curses.A_NORMAL if s.is_dark else curses.color_pair(2)
    wx_attr = curses.A_NORMAL if s.good_weather else curses.color_pair(2)

    row = r.y + 1
    _safe_addstr(stdscr, row, r.x + 1, "power: ")
    _safe_addstr(stdscr, row, r.x + 8, power_str, power_attr)
    _safe_addstr(stdscr, row, r.x + 12, "  dark: ")
    _safe_addstr(stdscr, row, r.x + 20, dark_str, dark_attr)
    _safe_addstr(stdscr, row, r.x + 24, "  weather: ")
    _safe_addstr(stdscr, row, r.x + 35, wx_str, wx_attr)

    if r.h > 2:
        _safe_addstr(
            stdscr,
            row + 1,
            r.x + 1,
            f"root: {s.free_space_root:.0f}% free  images: {s.free_space_images:.0f}% free",
        )


def render_mount_panel(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render mount status in ``layout.left_mid``."""
    r = layout.left_mid
    _safe_addstr(stdscr, r.y, r.x, "─" * r.w)
    _safe_addstr(stdscr, r.y, r.x + 2, " MOUNT ", curses.A_BOLD)

    m = model.mount
    conn_attr = curses.A_NORMAL if m.connected else curses.color_pair(2)

    if not m.connected:
        _safe_addstr(stdscr, r.y + 1, r.x + 1, "NOT CONNECTED", conn_attr)
        return

    state_parts: list[str] = []
    if m.is_parked:
        state_parts.append("parked")
    if m.is_tracking:
        state_parts.append("tracking")
    if m.is_slewing:
        state_parts.append("slewing")
    state_str = "  ".join(state_parts) if state_parts else "idle"

    _safe_addstr(stdscr, r.y + 1, r.x + 1, state_str)
    if r.h > 2:
        _safe_addstr(stdscr, r.y + 2, r.x + 1, f"ra={m.ra}  dec={m.dec}  ha={m.ha}")
    if r.h > 3:
        _safe_addstr(stdscr, r.y + 3, r.x + 1, f"alt={m.alt}  az={m.az}")


def render_observation_panel(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render the current observation in ``layout.right_top``."""
    r = layout.right_top
    _safe_addstr(stdscr, r.y, r.x, "─" * r.w)
    _safe_addstr(stdscr, r.y, r.x + 2, " OBSERVATION ", curses.A_BOLD)

    obs = model.scheduler.observing
    if not obs.field_name:
        _safe_addstr(stdscr, r.y + 1, r.x + 1, "No active observation")
        return

    _safe_addstr(stdscr, r.y + 1, r.x + 1, f"field: {obs.field_name}")
    if r.h > 2:
        _safe_addstr(stdscr, r.y + 2, r.x + 1, f"exp: {obs.current_exp_num}  exptime: {obs.exposure_s:.0f}s")


def render_cameras_panel(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render camera status in ``layout.right_mid``."""
    from panoptes.pocs.tui.theme import sparkline

    r = layout.right_mid
    _safe_addstr(stdscr, r.y, r.x, "─" * r.w)
    _safe_addstr(stdscr, r.y, r.x + 2, " CAMERAS ", curses.A_BOLD)

    if not model.cameras:
        _safe_addstr(stdscr, r.y + 1, r.x + 1, "No cameras connected")
        return

    row = r.y + 1
    for cam in model.cameras:
        if row >= r.y + r.h:
            break
        status = "exposing" if cam.is_exposing else "idle"
        line = f"{cam.name[:12]}  {status}  temp={cam.temperature}  filter={cam.filter_name}"
        _safe_addstr(stdscr, row, r.x + 1, line)
        row += 1
        if row < r.y + r.h and cam.progress_hist:
            spark = sparkline(list(cam.progress_hist), r.w - 3)
            _safe_addstr(stdscr, row, r.x + 2, spark)
            row += 1


def render_cmdlog_panel(stdscr: Any, layout: Layout, cmdlog: Any) -> None:
    """Render the latest command log entries."""
    r = layout.cmdlog
    _safe_addstr(stdscr, r.y, r.x, "─" * r.w)
    _safe_addstr(stdscr, r.y, r.x + 2, " LOG ", curses.A_BOLD)

    entries = cmdlog.tail(r.h - 1)
    for i, entry in enumerate(entries):
        row = r.y + 1 + i
        if row >= r.y + r.h:
            break
        line = f"{entry.ts}  {entry.level:<5}  {entry.msg}"
        _safe_addstr(stdscr, row, r.x + 1, line)


def render_modal(stdscr: Any, layout: Layout, model: POCSModel) -> None:
    """Render the confirmation modal overlay if active."""
    if not model.modal.active:
        return

    r = layout.modal
    try:
        stdscr.attron(curses.A_REVERSE)
        for row in range(r.y, r.y + r.h):
            stdscr.addstr(row, r.x, " " * r.w)
        stdscr.attroff(curses.A_REVERSE)
    except curses.error:
        pass

    modal = model.modal
    mid_y = r.y + r.h // 2 - 1
    _safe_addstr(stdscr, mid_y, r.x + 2, modal.prompt, curses.A_BOLD | curses.A_REVERSE)

    cx = r.x + 2
    for i, choice in enumerate(modal.choices):
        attr = curses.A_NORMAL if i != modal.selected else curses.A_BOLD
        _safe_addstr(stdscr, mid_y + 2, cx, f"[{choice}]", attr | curses.A_REVERSE)
        cx += len(choice) + 5


def render_dashboard(stdscr: Any, layout: Layout, model: POCSModel, cmdlog: Any) -> None:
    """Render the full dashboard view."""
    render_safety_panel(stdscr, layout, model)
    render_mount_panel(stdscr, layout, model)
    render_observation_panel(stdscr, layout, model)
    render_cameras_panel(stdscr, layout, model)
    render_cmdlog_panel(stdscr, layout, cmdlog)
