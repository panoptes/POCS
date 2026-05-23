"""Layout dataclasses and view/focus enums for the TUI skeleton."""

from dataclasses import dataclass, field
from enum import IntEnum


class View(IntEnum):
    """Main views selected via function keys."""

    DASHBOARD = 1
    HARDWARE = 2
    SCHEDULER = 3
    SAFETY = 4
    HELP = 5


class Focus(IntEnum):
    """Keyboard focus targets used by navigation input."""

    NONE = 0
    PANELS = 1
    FILTER = 2
    CMDLOG = 3


@dataclass(slots=True)
class Rect:
    """A rectangular region inside the curses screen."""

    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


@dataclass(slots=True)
class Layout:
    """Calculated panel geometry for the active view."""

    width: int = 0
    height: int = 0
    active_view: View = View.DASHBOARD
    focus: Focus = Focus.NONE
    screen: Rect = field(default_factory=Rect)
    header: Rect = field(default_factory=Rect)
    footer: Rect = field(default_factory=Rect)
    status_bar: Rect = field(default_factory=Rect)
    filter_bar: Rect = field(default_factory=Rect)
    left_top: Rect = field(default_factory=Rect)
    right_top: Rect = field(default_factory=Rect)
    left_mid: Rect = field(default_factory=Rect)
    right_mid: Rect = field(default_factory=Rect)
    cmdlog: Rect = field(default_factory=Rect)


def layout_compute(lay: Layout) -> None:
    """Compute panel rectangles from ``lay.width`` and ``lay.height``.

    TODO: Implement full geometry calculation for all views and resize behavior.
    """
    return None
