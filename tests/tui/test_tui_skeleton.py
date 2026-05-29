"""Tests for the initial POCS TUI skeleton modules."""

from __future__ import annotations

import curses

from panoptes.pocs.tui.actions import action_park, action_quit
from panoptes.pocs.tui.bridge import Bridge
from panoptes.pocs.tui.cmdlog import CmdLog
from panoptes.pocs.tui.input import handle
from panoptes.pocs.tui.layout import Focus, Layout, View, layout_compute
from panoptes.pocs.tui.model import SPARKLINE_LEN, CameraModel, POCSModel, SystemModel
from panoptes.pocs.tui.panels.operations import menu_next, menu_prev
from panoptes.pocs.tui.scanner import Scanner
from panoptes.pocs.tui.theme import SPARK_CHARS, sparkline


class _MockPocs:
    """Minimal POCS stub for bridge tests."""

    def __init__(self) -> None:
        self.state = "sleeping"


class _MockBridge:
    """Minimal bridge stub for action tests."""

    def park(self) -> None:
        """No-op park implementation."""


def test_model_defaults() -> None:
    """POCSModel should expose stable default values for all top-level panels."""
    model = POCSModel()

    assert model.system.state == "unknown"
    assert model.mount.is_parked is True
    assert model.scheduler.observing.field_name == ""
    assert model.cameras == []


def test_model_has_modal_and_config_editor() -> None:
    """POCSModel should include modal and config editor state."""
    model = POCSModel()

    assert model.modal.active is False
    assert model.config_editor.cursor == 0


def test_system_model_run_active() -> None:
    """SystemModel should default run activity to False."""
    assert SystemModel().run_active is False


def test_camera_progress_buffer_length() -> None:
    """Camera progress history should use the shared fixed sparkline length."""
    camera = CameraModel()
    assert camera.progress_hist.maxlen == SPARKLINE_LEN


def test_cmdlog_push_and_tail() -> None:
    """CmdLog should retain recent entries in insertion order."""
    cmdlog = CmdLog()
    cmdlog.push("INFO", "one")
    cmdlog.push("WARN", "two")

    entries = cmdlog.tail(1)
    assert len(entries) == 1
    assert entries[0].msg == "two"


def test_sparkline_width() -> None:
    """Sparkline helper should honor requested width."""
    out = sparkline([0.0, 0.5, 1.0], width=5)
    assert len(out) == 5
    assert set(out).issubset(set(SPARK_CHARS))


def test_layout_defaults() -> None:
    """Layout should default to dashboard view with no focus and zeroed rects."""
    layout = Layout()

    assert layout.active_view is View.DASHBOARD
    assert layout.focus is Focus.NONE
    assert layout.screen.w == 0
    assert layout.cmdlog.h == 0


def test_layout_compute_basic() -> None:
    """Layout computation should populate core screen regions."""
    layout = Layout(width=120, height=40)

    layout_compute(layout)

    assert layout.tab_bar.h == 1
    assert layout.status_bar.h == 1
    assert layout.main.h > 0
    assert layout.cmdlog.h > 0
    assert layout.modal.w > 0
    assert layout.modal.h > 0


def test_scanner_snapshot_defaults() -> None:
    """Scanner snapshot should return an initialized model even before scans run."""
    scanner = Scanner(interval_s=0.01)
    scanner.start()
    snapshot = scanner.snapshot()
    scanner.stop()

    assert isinstance(snapshot, POCSModel)
    assert snapshot.scan_count >= 0


def test_bridge_offline() -> None:
    """Bridge should report offline status when no POCS is attached."""
    bridge = Bridge()
    try:
        assert bridge.is_connected is False
        assert bridge.pocs_state == "offline"
    finally:
        bridge.shutdown()


def test_bridge_connect() -> None:
    """Bridge should expose the connected POCS state."""
    bridge = Bridge()
    try:
        bridge.connect(_MockPocs())
        assert bridge.pocs_state == "sleeping"
    finally:
        bridge.shutdown()


def test_action_quit_sets_modal() -> None:
    """Quit action should open a confirmation modal."""
    bridge = Bridge()
    cmdlog = CmdLog()
    model = POCSModel()
    try:
        action_quit(bridge, cmdlog, model)
        assert model.modal.active is True
    finally:
        bridge.shutdown()


def test_action_park_logs() -> None:
    """Park action should record an operator-visible log entry."""
    cmdlog = CmdLog()

    action_park(_MockBridge(), cmdlog)

    messages = [entry.msg for entry in cmdlog.tail(10)]
    assert any("Park requested" in msg for msg in messages)


def test_operations_menu_navigation() -> None:
    """Menu navigation should skip separator rows."""
    assert menu_next(2) == 4
    assert menu_prev(8) == 6


def test_input_handle_navigation() -> None:
    """Input handling should map navigation keys."""
    assert handle(curses.KEY_UP) == "up"
    assert handle(ord("q")) == "quit"
