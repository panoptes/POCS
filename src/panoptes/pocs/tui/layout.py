"""Layout dataclasses and view/focus enums for the TUI skeleton."""

from dataclasses import dataclass, field
from enum import IntEnum


class View(IntEnum):
    """Main views selected via function keys."""

    DASHBOARD = 1
    HARDWARE = 2
    SCHEDULER = 3
    OPERATIONS = 4
    CONFIG = 5
    HELP = 6


class Focus(IntEnum):
    """Keyboard focus targets used by navigation input."""

    NONE = 0
    PANELS = 1
    MENU = 2
    CONFIG_EDITOR = 3
    MODAL = 4


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
    tab_bar: Rect = field(default_factory=Rect)
    status_bar: Rect = field(default_factory=Rect)
    main: Rect = field(default_factory=Rect)
    cmdlog: Rect = field(default_factory=Rect)
    nav_bar: Rect = field(default_factory=Rect)
    left_top: Rect = field(default_factory=Rect)
    right_top: Rect = field(default_factory=Rect)
    left_mid: Rect = field(default_factory=Rect)
    right_mid: Rect = field(default_factory=Rect)
    modal: Rect = field(default_factory=Rect)


def layout_compute(lay: Layout) -> None:
    """Compute panel rectangles from ``lay.width`` and ``lay.height``.

    Args:
        lay: Mutable layout object to populate.
    """
    width = max(lay.width, 0)
    height = max(lay.height, 0)

    lay.screen = Rect(x=0, y=0, w=width, h=height)
    lay.tab_bar = Rect(x=0, y=0, w=width, h=1 if height > 0 else 0)
    lay.status_bar = Rect(x=0, y=1 if height > 1 else 0, w=width, h=1 if height > 1 else 0)

    main_y = 2 if height > 2 else height
    main_h = max(height - 5, 0)
    lay.main = Rect(x=0, y=main_y, w=width, h=main_h)

    cmdlog_y = max(height - 3, 0)
    cmdlog_h = 2 if height >= 2 else max(height, 0)
    lay.cmdlog = Rect(x=0, y=cmdlog_y, w=width, h=cmdlog_h)
    lay.nav_bar = Rect(x=0, y=max(height - 1, 0), w=width, h=1 if height > 0 else 0)

    left_w = lay.main.w // 2
    right_w = lay.main.w - left_w
    top_h = lay.main.h // 2
    bottom_h = lay.main.h - top_h

    lay.left_top = Rect(x=lay.main.x, y=lay.main.y, w=left_w, h=top_h)
    lay.right_top = Rect(x=lay.main.x + left_w, y=lay.main.y, w=right_w, h=top_h)
    lay.left_mid = Rect(x=lay.main.x, y=lay.main.y + top_h, w=left_w, h=bottom_h)
    lay.right_mid = Rect(x=lay.main.x + left_w, y=lay.main.y + top_h, w=right_w, h=bottom_h)

    modal_w = min(width, max(40, int(width * 0.6))) if width > 0 else 0
    modal_h = min(height, max(10, int(height * 0.4))) if height > 0 else 0
    lay.modal = Rect(
        x=max((width - modal_w) // 2, 0),
        y=max((height - modal_h) // 2, 0),
        w=modal_w,
        h=modal_h,
    )
