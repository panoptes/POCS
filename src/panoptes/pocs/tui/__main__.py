"""Entry points and render-loop skeleton for the POCS TUI."""

from __future__ import annotations

import curses
from time import sleep

from panoptes.pocs.tui.cmdlog import CmdLog
from panoptes.pocs.tui.layout import Layout, layout_compute
from panoptes.pocs.tui.scanner import Scanner
from panoptes.pocs.tui.theme import init_colors

FPS = 20


def _render_header(stdscr, _layout: Layout) -> None:
    stdscr.addstr(0, 0, "POCS TUI (skeleton)  F1-DASHBOARD F2-HARDWARE F3-SCHEDULER F4-SAFETY F5-HELP")


def _render_active_panel(stdscr, layout: Layout) -> None:
    stdscr.addstr(2, 0, f"Active view: {layout.active_view.name}")


def _render_footer(stdscr, _layout: Layout) -> None:
    stdscr.addstr(curses.LINES - 1, 0, "q=quit  p=park  a=abort  /=filter  ?=help")


def main(stdscr, pocs=None) -> None:
    """Run the curses render loop for the TUI skeleton."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    init_colors(stdscr)

    scanner = Scanner(pocs=pocs, interval_s=0.5)
    layout = Layout()
    _cmdlog = CmdLog()
    scanner.start()

    try:
        running = True
        while running:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                running = False

            _ = scanner.snapshot()
            height, width = stdscr.getmaxyx()
            layout.width = width
            layout.height = height
            layout_compute(layout)

            stdscr.erase()
            _render_header(stdscr, layout)
            _render_active_panel(stdscr, layout)
            _render_footer(stdscr, layout)
            stdscr.refresh()
            sleep(1 / FPS)
    finally:
        scanner.stop()


def curses_main() -> None:
    """Launch the curses application wrapper."""
    curses.wrapper(main)


if __name__ == "__main__":
    curses_main()
