"""Theme constants and helpers for the TUI skeleton."""

import curses
from collections.abc import Sequence

SPARK_CHARS = "▁▂▃▄▅▆▇█"

COLOR_PAIRS = {
    "default": (curses.COLOR_WHITE, curses.COLOR_BLACK),
    "title": (curses.COLOR_CYAN, curses.COLOR_BLACK),
    "ok": (curses.COLOR_GREEN, curses.COLOR_BLACK),
    "warn": (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    "error": (curses.COLOR_RED, curses.COLOR_BLACK),
    "dim": (curses.COLOR_BLUE, curses.COLOR_BLACK),
}


def init_colors(stdscr) -> dict[str, int]:
    """Initialize curses color pairs and return pair IDs by semantic name."""
    if not curses.has_colors():
        return {name: 0 for name in COLOR_PAIRS}

    curses.start_color()
    curses.use_default_colors()

    pair_ids: dict[str, int] = {}
    for pair_id, (name, (fg, bg)) in enumerate(COLOR_PAIRS.items(), start=1):
        curses.init_pair(pair_id, fg, bg)
        pair_ids[name] = pair_id

    stdscr.attrset(curses.color_pair(pair_ids["default"]))
    return pair_ids


def sparkline(values: Sequence[float], width: int) -> str:
    """Render a bounded-width unicode sparkline from numeric samples."""
    if width <= 0:
        return ""

    if not values:
        return " " * width

    clipped = list(values)[-width:]
    if len(clipped) < width:
        clipped = [0.0] * (width - len(clipped)) + clipped

    minimum = min(clipped)
    maximum = max(clipped)
    span = maximum - minimum

    if span <= 0:
        return SPARK_CHARS[0] * width

    last_idx = len(SPARK_CHARS) - 1
    return "".join(
        SPARK_CHARS[min(last_idx, int(((value - minimum) / span) * last_idx))] for value in clipped
    )
