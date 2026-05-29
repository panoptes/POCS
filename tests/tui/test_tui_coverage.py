"""Extended coverage tests for the POCS TUI modules.

Covers actions, bridge, scanner, operations, theme, cmdlog, and
the curses rendering panels using mock screens.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from panoptes.pocs.tui.cmdlog import CmdLog
from panoptes.pocs.tui.model import CameraModel, POCSModel
from panoptes.pocs.tui.panels.dashboard import (
    _safe_addstr,
    render_cameras_panel,
    render_cmdlog_panel,
    render_dashboard,
    render_modal,
    render_mount_panel,
    render_nav_bar,
    render_observation_panel,
    render_safety_panel,
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

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_screen(rows: int = 40, cols: int = 120) -> MagicMock:
    """Return a mock curses screen with given dimensions."""
    screen = MagicMock()
    screen.getmaxyx.return_value = (rows, cols)
    return screen


def _computed_layout(width: int = 120, height: int = 40):
    from panoptes.pocs.tui.layout import Layout, layout_compute

    layout = Layout(width=width, height=height)
    layout_compute(layout)
    return layout


@dataclass
class _MockEvent:
    """Minimal TelemetryEvent stand-in."""

    data: dict
    ts: str = "2026-01-01T00:00:00"
    seq: int = 1
    meta: dict = field(default_factory=dict)


class _MockTelemetryClient:
    """Telemetry client that returns a rich set of events."""

    def current(self) -> dict[str, _MockEvent]:
        return {
            "status": _MockEvent(
                {
                    "state": "tracking",
                    "next_state": "observing",
                    "run_active": True,
                    "do_states": True,
                    "observatory": {
                        "can_observe": True,
                        "mount": {
                            "is_parked": False,
                            "is_tracking": True,
                            "is_slewing": False,
                            "ra": "12:00:00",
                            "dec": "+45:00:00",
                            "current_ha": 1.5,
                            "alt": 45.0,
                            "az": 180.0,
                        },
                        "cameras": {
                            "cam1": {
                                "is_exposing": True,
                                "temperature": -10.0,
                                "filter_name": "L",
                            }
                        },
                        "current_observation": {
                            "field_name": "M31",
                            "exp_time": 120.0,
                            "current_exp": 3,
                        },
                    },
                }
            ),
            "weather": _MockEvent({"safe": True, "is_dark": True}),
            "power": _MockEvent({"main": True}),
            "state": _MockEvent({"dest": "observing", "do_states": True, "is_dark": True}),
        }


class _ErrorTelemetryClient:
    """Telemetry client that always raises."""

    def current(self) -> dict:
        raise ConnectionRefusedError("no server")


class _MockPocs:
    """Minimal POCS stub."""

    state = "sleeping"
    do_states = False

    def initialize(self) -> None: ...

    def run(self) -> None: ...

    def stop_states(self) -> None: ...

    def power_down(self) -> None: ...


class _BrokenPocsProp:
    """POCS where .state always raises."""

    @property
    def state(self) -> str:
        raise RuntimeError("hardware gone")


class _MockBridge:
    """Bridge stub for action tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def initialize(self) -> None:
        self.calls.append("initialize")

    def start_run(self) -> None:
        self.calls.append("start_run")

    def stop_run(self) -> None:
        self.calls.append("stop_run")

    def park(self) -> None:
        self.calls.append("park")

    def abort_exposure(self) -> None:
        self.calls.append("abort_exposure")

    def power_down(self) -> None:
        self.calls.append("power_down")

    def set_config(self, key: str, value: Any) -> bool:
        self.calls.append(f"set_config:{key}")
        return True

    def set_config_fail(self, key: str, value: Any) -> bool:
        return False


# ---------------------------------------------------------------------------
# cmdlog
# ---------------------------------------------------------------------------


class TestCmdLog:
    def test_tail_zero_returns_empty(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        log = CmdLog()
        log.push("INFO", "msg")
        assert log.tail(0) == []

    def test_tail_more_than_available(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        log = CmdLog()
        log.push("INFO", "only one")
        assert len(log.tail(100)) == 1

    def test_push_returns_entry(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        log = CmdLog()
        entry = log.push("WARN", "something")
        assert entry.level == "WARN"
        assert entry.msg == "something"


# ---------------------------------------------------------------------------
# theme
# ---------------------------------------------------------------------------


class TestSparkline:
    def test_zero_width_returns_empty(self) -> None:
        from panoptes.pocs.tui.theme import sparkline

        assert sparkline([1.0, 2.0], width=0) == ""

    def test_empty_values_returns_spaces(self) -> None:
        from panoptes.pocs.tui.theme import sparkline

        result = sparkline([], width=5)
        assert result == "     "

    def test_flat_values_uses_lowest_char(self) -> None:
        from panoptes.pocs.tui.theme import SPARK_CHARS, sparkline

        result = sparkline([5.0, 5.0, 5.0], width=3)
        assert result == SPARK_CHARS[0] * 3

    def test_pads_when_fewer_values_than_width(self) -> None:
        from panoptes.pocs.tui.theme import sparkline

        result = sparkline([1.0], width=5)
        assert len(result) == 5

    def test_clips_when_more_values_than_width(self) -> None:
        from panoptes.pocs.tui.theme import sparkline

        result = sparkline([0.0] * 20, width=5)
        assert len(result) == 5


class TestInitColors:
    def test_no_color_support_returns_zeros(self) -> None:
        from panoptes.pocs.tui.theme import init_colors

        with patch("curses.has_colors", return_value=False):
            result = init_colors(_mock_screen())
        assert all(v == 0 for v in result.values())
        assert "default" in result

    def test_with_color_support_returns_pair_ids(self) -> None:
        from panoptes.pocs.tui.theme import COLOR_PAIRS, init_colors

        with (
            patch("curses.has_colors", return_value=True),
            patch("curses.start_color"),
            patch("curses.use_default_colors"),
            patch("curses.init_pair"),
            patch("curses.color_pair", return_value=curses.A_NORMAL),
        ):
            screen = _mock_screen()
            result = init_colors(screen)

        assert set(result.keys()) == set(COLOR_PAIRS.keys())
        screen.attrset.assert_called_once()


# ---------------------------------------------------------------------------
# scanner._fmt_float
# ---------------------------------------------------------------------------


class TestFmtFloat:
    def test_valid_float(self) -> None:
        from panoptes.pocs.tui.scanner import _fmt_float

        assert _fmt_float(3.14159) == "3.14"

    def test_string_float(self) -> None:
        from panoptes.pocs.tui.scanner import _fmt_float

        assert _fmt_float("2.5") == "2.50"

    def test_invalid_string_returns_dashes(self) -> None:
        from panoptes.pocs.tui.scanner import _fmt_float

        assert _fmt_float("not-a-number") == "--"

    def test_none_returns_dashes(self) -> None:
        from panoptes.pocs.tui.scanner import _fmt_float

        assert _fmt_float(None) == "--"


# ---------------------------------------------------------------------------
# scanner.Scanner._scan
# ---------------------------------------------------------------------------


class TestScannerScan:
    def test_scan_populates_model_from_telemetry(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(interval_s=0.01)
        scanner._client = _MockTelemetryClient()
        model = scanner._scan()

        # state_event.dest overrides status_event.state
        assert model.system.state == "observing"
        assert model.system.run_active is True
        assert model.system.connected is True

        assert model.mount.is_tracking is True
        assert model.mount.is_parked is False
        assert model.mount.ra == "12:00:00"
        assert model.mount.ha == "1.50"
        assert model.mount.alt == "45.00"

        assert len(model.cameras) == 1
        assert model.cameras[0].name == "cam1"
        assert model.cameras[0].is_exposing is True
        assert model.cameras[0].temperature == "-10.00"
        assert model.cameras[0].filter_name == "L"

        assert model.scheduler.observing.field_name == "M31"
        assert model.scheduler.observing.exposure_s == 120.0
        assert model.scheduler.observing.current_exp_num == 3

        assert model.safety.good_weather is True
        assert model.safety.is_dark is True
        assert model.safety.ac_power is True

    def test_scan_returns_empty_model_on_client_error(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(interval_s=0.01)
        scanner._client = _ErrorTelemetryClient()
        model = scanner._scan()

        assert model.system.state == "unknown"
        assert model.cameras == []

    def test_force_update_wakes_scanner(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(interval_s=10.0)
        scanner.start()
        scanner.force_update()
        scanner.stop()

    def test_scan_skips_missing_optional_events(self) -> None:
        """Scanner should handle missing weather/power/state events gracefully."""
        from panoptes.pocs.tui.scanner import Scanner

        class _MinimalClient:
            def current(self):
                return {}  # no events at all

        scanner = Scanner(interval_s=0.01)
        scanner._client = _MinimalClient()
        model = scanner._scan()
        assert model.system.state == "unknown"


# ---------------------------------------------------------------------------
# Scanner._scan_direct
# ---------------------------------------------------------------------------


class _MockMount:
    """Minimal mount stub for direct-read tests."""

    is_parked = False
    is_tracking = True
    is_slewing = False
    is_initialized = True


class _MockCamera:
    """Minimal camera stub for direct-read tests."""

    is_connected = True
    is_exposing = False
    temperature = -15.5
    filter_name = "Ha"


class _MockObservation:
    """Minimal observation stub for direct-read tests."""

    @property
    def status(self) -> dict:
        return {"field_name": "Andromeda", "exptime": 60.0, "current_exp": 2}


class _FullPocs:
    """POCS stub with enough structure for _scan_direct to populate a model."""

    state = "observing"
    next_state = "tracking"
    do_states = True

    @property
    def status(self) -> dict:
        return {
            "state": self.state,
            "next_state": self.next_state,
            "observatory": {
                "can_observe": True,
                "mount": {
                    "current_ra": 183.5,
                    "current_dec": 12.3,
                    "current_ha": 0.75,
                    "alt": 55.1,
                    "az": 200.0,
                },
                "observation": {
                    "field_name": "Andromeda",
                    "exptime": 60.0,
                    "current_exp": 2,
                },
            },
        }

    class _Observatory:
        mount = _MockMount()
        cameras = {"cam_a": _MockCamera()}
        can_observe = True
        current_observation = _MockObservation()

    observatory = _Observatory()


class _ErrorPocs:
    """POCS stub whose .status raises."""

    @property
    def status(self) -> dict:
        raise RuntimeError("hardware error")


class TestScannerDirect:
    def test_scan_direct_preferred_when_pocs_present(self) -> None:
        """When pocs is provided, _scan() uses _scan_direct() not the telemetry client."""
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_FullPocs(), interval_s=0.01)
        # Provide an error client so we'd notice if it were used.
        scanner._client = _ErrorTelemetryClient()
        model = scanner._scan()
        assert model.system.state == "observing"

    def test_scan_direct_state_and_run_active(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_FullPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert model.system.state == "observing"
        assert model.system.next_state == "tracking"
        assert model.system.run_active is True
        assert model.system.connected is True

    def test_scan_direct_mount_fields(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_FullPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert model.mount.is_tracking is True
        assert model.mount.is_parked is False
        assert model.mount.is_slewing is False
        assert model.mount.connected is True
        # ha/alt/az require get_current_coordinates() on mount — mock has none, so "--"
        assert model.mount.ha == "--"
        assert model.mount.alt == "--"
        assert model.mount.az == "--"

    def test_scan_direct_camera_fields(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_FullPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert len(model.cameras) == 1
        cam = model.cameras[0]
        assert cam.name == "cam_a"
        assert cam.connected is True
        assert cam.is_exposing is False
        assert cam.temperature == "-15.50"
        assert cam.filter_name == "Ha"

    def test_scan_direct_observation_fields(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_FullPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert model.scheduler.selected_field == "Andromeda"
        assert model.scheduler.observing.field_name == "Andromeda"
        assert model.scheduler.observing.exposure_s == 60.0
        assert model.scheduler.observing.current_exp_num == 2

    def test_scan_direct_returns_empty_model_on_status_error(self) -> None:
        from panoptes.pocs.tui.scanner import Scanner

        scanner = Scanner(pocs=_ErrorPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert model.system.state == "unknown"
        assert model.cameras == []

    def test_scan_direct_handles_no_observatory(self) -> None:
        """POCS without observatory should still return a valid model."""
        from panoptes.pocs.tui.scanner import Scanner

        class _MinimalPocs:
            state = "sleeping"
            next_state = ""
            do_states = False

            @property
            def status(self) -> dict:
                return {"state": "sleeping", "next_state": ""}

        scanner = Scanner(pocs=_MinimalPocs(), interval_s=0.01)
        model = scanner._scan_direct()
        assert model.system.state == "sleeping"
        assert model.cameras == []


# ---------------------------------------------------------------------------
# bridge.Bridge
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_initialize_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.initialize()  # should not raise

    def test_initialize_submits_to_executor(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()
        bridge._executor = MagicMock()
        bridge.initialize()
        bridge._executor.submit.assert_called_once_with(bridge._pocs.initialize)

    def test_stop_run_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.stop_run()

    def test_stop_run_submits_stop_states(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()
        bridge._executor = MagicMock()
        bridge.stop_run()
        bridge._executor.submit.assert_called_once_with(bridge._pocs.stop_states)

    def test_start_run_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.start_run()
        assert bridge._run_thread is None

    def test_start_run_creates_thread(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        try:
            bridge._pocs = _MockPocs()
            bridge.start_run()
            assert bridge._run_thread is not None
        finally:
            bridge.shutdown()

    def test_run_active_no_pocs(self) -> None:
        bridge = _create_bridge()
        assert bridge.run_active is False

    def test_run_active_do_states_false(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()  # do_states=False
        assert bridge.run_active is False
        bridge.shutdown()

    def test_run_active_with_alive_thread(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        mock_pocs = MagicMock(do_states=True)
        bridge._pocs = mock_pocs
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        bridge._run_thread = mock_thread
        assert bridge.run_active is True
        bridge.shutdown()

    def test_park_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.park()

    def test_park_submits(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()
        bridge._executor = MagicMock()
        bridge.park()
        bridge._executor.submit.assert_called_once()

    def test_abort_exposure_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.abort_exposure()

    def test_abort_exposure_submits(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()
        bridge._executor = MagicMock()
        bridge.abort_exposure()
        bridge._executor.submit.assert_called_once()

    def test_power_down_no_pocs_is_noop(self) -> None:
        bridge = _create_bridge()
        bridge.power_down()

    def test_power_down_submits(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _MockPocs()
        bridge._executor = MagicMock()
        bridge.power_down()
        bridge._executor.submit.assert_called_once_with(bridge._pocs.power_down)

    def test_park_inner_function_sets_next_state(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        mock_pocs = MagicMock()
        bridge._pocs = mock_pocs
        bridge._executor = MagicMock()
        bridge.park()
        submitted_fn = bridge._executor.submit.call_args[0][0]
        submitted_fn()
        assert mock_pocs.next_state == "parking"
        bridge.shutdown()

    def test_park_inner_function_swallows_exception(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()

        class _PocsParkFails:
            @property
            def next_state(self):
                return None

            @next_state.setter
            def next_state(self, _):
                raise RuntimeError("mount busy")

        bridge._pocs = _PocsParkFails()
        bridge._executor = MagicMock()
        bridge.park()
        submitted_fn = bridge._executor.submit.call_args[0][0]
        submitted_fn()  # should not raise

    def test_abort_exposure_inner_function_stops_exposing_camera(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        mock_cam = MagicMock()
        mock_cam.is_exposing = True
        mock_obs = MagicMock()
        mock_obs.cameras = {"cam1": mock_cam}
        mock_pocs = MagicMock()
        mock_pocs.observatory = mock_obs
        bridge._pocs = mock_pocs
        bridge._executor = MagicMock()
        bridge.abort_exposure()
        submitted_fn = bridge._executor.submit.call_args[0][0]
        submitted_fn()
        mock_cam.stop_observing.set.assert_called_once()

    def test_abort_exposure_inner_function_skips_idle_camera(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        mock_cam = MagicMock()
        mock_cam.is_exposing = False
        mock_obs = MagicMock()
        mock_obs.cameras = {"cam1": mock_cam}
        mock_pocs = MagicMock()
        mock_pocs.observatory = mock_obs
        bridge._pocs = mock_pocs
        bridge._executor = MagicMock()
        bridge.abort_exposure()
        submitted_fn = bridge._executor.submit.call_args[0][0]
        submitted_fn()
        mock_cam.stop_observing.set.assert_not_called()
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        bridge._pocs = _BrokenPocsProp()
        assert bridge.pocs_state == "unknown"
        bridge.shutdown()

    def test_get_config_success(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        with patch("panoptes.pocs.tui.bridge.get_config", return_value="panoptes"):
            result = bridge.get_config("name")
        assert result == "panoptes"
        bridge.shutdown()

    def test_get_config_exception_returns_default(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        with patch("panoptes.pocs.tui.bridge.get_config", side_effect=RuntimeError("fail")):
            result = bridge.get_config("name", default="fallback")
        assert result == "fallback"
        bridge.shutdown()

    def test_set_config_success(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        with patch("panoptes.pocs.tui.bridge.set_config") as mock_set:
            result = bridge.set_config("name", "my-unit")
        assert result is True
        mock_set.assert_called_once_with("name", "my-unit", persist=True)
        bridge.shutdown()

    def test_set_config_exception_returns_false(self) -> None:
        from panoptes.pocs.tui.bridge import Bridge

        bridge = Bridge()
        with patch("panoptes.pocs.tui.bridge.set_config", side_effect=RuntimeError("disk full")):
            result = bridge.set_config("name", "my-unit")
        assert result is False
        bridge.shutdown()


def _create_bridge():
    from panoptes.pocs.tui.bridge import Bridge

    b = Bridge()
    b.shutdown()
    return b


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------


class TestActions:
    def test_action_initialize_calls_bridge(self) -> None:
        from panoptes.pocs.tui.actions import action_initialize

        bridge = _MockBridge()
        action_initialize(bridge, CmdLog())
        assert "initialize" in bridge.calls

    def test_action_initialize_logs(self) -> None:
        from panoptes.pocs.tui.actions import action_initialize

        log = CmdLog()
        action_initialize(_MockBridge(), log)
        assert any("Initialize" in e.msg for e in log.tail(5))

    def test_action_start_run_calls_bridge(self) -> None:
        from panoptes.pocs.tui.actions import action_start_run

        bridge = _MockBridge()
        action_start_run(bridge, CmdLog())
        assert "start_run" in bridge.calls

    def test_action_stop_run_sets_modal_with_model(self) -> None:
        from panoptes.pocs.tui.actions import action_stop_run

        model = POCSModel()
        action_stop_run(_MockBridge(), CmdLog(), model)
        assert model.modal.active is True
        assert model.modal.callback == "action_stop_run_confirmed"

    def test_action_stop_run_calls_bridge_without_model(self) -> None:
        from panoptes.pocs.tui.actions import action_stop_run

        bridge = _MockBridge()
        action_stop_run(bridge, CmdLog(), None)
        assert "stop_run" in bridge.calls

    def test_action_stop_run_confirmed_calls_bridge(self) -> None:
        from panoptes.pocs.tui.actions import action_stop_run_confirmed

        bridge = _MockBridge()
        action_stop_run_confirmed(bridge, CmdLog())
        assert "stop_run" in bridge.calls

    def test_action_power_down_sets_modal_with_model(self) -> None:
        from panoptes.pocs.tui.actions import action_power_down

        model = POCSModel()
        action_power_down(_MockBridge(), CmdLog(), model)
        assert model.modal.active is True
        assert model.modal.callback == "action_power_down_confirmed"

    def test_action_power_down_calls_bridge_without_model(self) -> None:
        from panoptes.pocs.tui.actions import action_power_down

        bridge = _MockBridge()
        action_power_down(bridge, CmdLog(), None)
        assert "power_down" in bridge.calls

    def test_action_power_down_confirmed_calls_bridge(self) -> None:
        from panoptes.pocs.tui.actions import action_power_down_confirmed

        bridge = _MockBridge()
        action_power_down_confirmed(bridge, CmdLog())
        assert "power_down" in bridge.calls

    def test_action_quit_confirmed_sets_sentinel(self) -> None:
        from panoptes.pocs.tui.actions import action_quit_confirmed

        model = POCSModel()
        action_quit_confirmed(_MockBridge(), CmdLog(), model)
        assert model.system.state == "__quit__"

    def test_action_quit_confirmed_no_model_no_error(self) -> None:
        from panoptes.pocs.tui.actions import action_quit_confirmed

        action_quit_confirmed(_MockBridge(), CmdLog(), None)  # should not raise

    def test_action_abort_exposure_calls_bridge(self) -> None:
        from panoptes.pocs.tui.actions import action_abort_exposure

        bridge = _MockBridge()
        action_abort_exposure(bridge, CmdLog())
        assert "abort_exposure" in bridge.calls

    def test_action_snapshot_logs(self) -> None:
        from panoptes.pocs.tui.actions import action_snapshot

        log = CmdLog()
        action_snapshot(_MockBridge(), log)
        assert any("snapshot" in e.msg.lower() for e in log.tail(5))

    def test_action_set_config_success_logs(self) -> None:
        from panoptes.pocs.tui.actions import action_set_config

        log = CmdLog()
        action_set_config(_MockBridge(), log, key="name", value="test")
        assert any("Config updated" in e.msg for e in log.tail(5))

    def test_action_set_config_failure_logs_error(self) -> None:
        from panoptes.pocs.tui.actions import action_set_config

        class _FailBridge(_MockBridge):
            def set_config(self, key, value):
                return False

        log = CmdLog()
        action_set_config(_FailBridge(), log, key="name", value="test")
        assert any("failed" in e.msg.lower() for e in log.tail(5))

    def test_action_reload_config_logs(self) -> None:
        from panoptes.pocs.tui.actions import action_reload_config

        log = CmdLog()
        action_reload_config(_MockBridge(), log)
        assert any("reload" in e.msg.lower() for e in log.tail(5))

    def test_action_not_implemented_logs_label(self) -> None:
        from panoptes.pocs.tui.actions import action_not_implemented

        log = CmdLog()
        action_not_implemented(_MockBridge(), log, label="Polar alignment")
        assert any("Polar alignment" in e.msg for e in log.tail(5))

    def test_dispatch_known_action(self) -> None:
        from panoptes.pocs.tui.actions import dispatch

        bridge = _MockBridge()
        dispatch("action_park", bridge, CmdLog())
        assert "park" in bridge.calls

    def test_dispatch_polar_align_placeholder(self) -> None:
        from panoptes.pocs.tui.actions import dispatch

        log = CmdLog()
        dispatch("action_polar_align", _MockBridge(), log)
        assert any("Polar alignment" in e.msg for e in log.tail(5))

    def test_dispatch_focus_run_placeholder(self) -> None:
        from panoptes.pocs.tui.actions import dispatch

        log = CmdLog()
        dispatch("action_focus_run", _MockBridge(), log)
        assert any("Focus run" in e.msg for e in log.tail(5))

    def test_dispatch_take_darks_placeholder(self) -> None:
        from panoptes.pocs.tui.actions import dispatch

        log = CmdLog()
        dispatch("action_take_darks", _MockBridge(), log)
        assert any("dark" in e.msg.lower() for e in log.tail(5))

    def test_dispatch_unknown_action_no_error(self) -> None:
        from panoptes.pocs.tui.actions import dispatch

        dispatch("action_does_not_exist", _MockBridge(), CmdLog())  # should not raise


# ---------------------------------------------------------------------------
# panels.operations (non-rendering)
# ---------------------------------------------------------------------------


class TestOperationsMenu:
    def test_get_menu_action_first_item(self) -> None:
        assert get_menu_action(0) == "action_start_run"

    def test_get_menu_action_out_of_bounds_low(self) -> None:
        assert get_menu_action(-1) is None

    def test_get_menu_action_out_of_bounds_high(self) -> None:
        assert get_menu_action(9999) is None

    def test_menu_next_at_last_stays(self) -> None:
        last = SELECTABLE[-1]
        assert menu_next(last) == last

    def test_menu_prev_at_first_stays(self) -> None:
        first = SELECTABLE[0]
        assert menu_prev(first) == first

    def test_all_selectable_items_have_actions(self) -> None:
        from panoptes.pocs.tui.panels.operations import MENU_ITEMS

        for idx in SELECTABLE:
            _, action = MENU_ITEMS[idx]
            assert action is not None


# ---------------------------------------------------------------------------
# panels.dashboard  (rendering with mock screen)
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_color_pair():
    """Patch curses.color_pair so rendering tests don't need initscr()."""
    with patch("curses.color_pair", return_value=curses.A_NORMAL):
        yield


class TestSafeAddStr:
    def test_normal_call(self) -> None:
        screen = _mock_screen()
        _safe_addstr(screen, 5, 5, "hello")
        screen.addstr.assert_called_once()

    def test_y_out_of_bounds_no_call(self) -> None:
        screen = _mock_screen(rows=10, cols=80)
        _safe_addstr(screen, 10, 0, "text")
        screen.addstr.assert_not_called()

    def test_x_out_of_bounds_no_call(self) -> None:
        screen = _mock_screen(rows=10, cols=80)
        _safe_addstr(screen, 0, 80, "text")
        screen.addstr.assert_not_called()

    def test_negative_y_no_call(self) -> None:
        screen = _mock_screen()
        _safe_addstr(screen, -1, 0, "text")
        screen.addstr.assert_not_called()

    def test_text_clips_to_available_width(self) -> None:
        screen = _mock_screen(rows=10, cols=10)
        _safe_addstr(screen, 0, 5, "Hello World")
        args = screen.addstr.call_args[0]
        # text should be clipped to max_len = 10 - 5 - 1 = 4
        assert len(args[2]) <= 4

    def test_curses_error_suppressed(self) -> None:
        screen = _mock_screen()
        screen.addstr.side_effect = curses.error("test")
        _safe_addstr(screen, 0, 0, "text")  # should not raise


class TestDashboardRenderers:
    @pytest.fixture(autouse=True)
    def _color(self, patch_color_pair) -> None:
        pass

    def test_render_tab_bar(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        render_tab_bar(_mock_screen(), layout, model)

    def test_render_status_bar_idle(self) -> None:
        layout = _computed_layout()
        render_status_bar(_mock_screen(), layout, POCSModel())

    def test_render_status_bar_run_active(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.system.run_active = True
        render_status_bar(_mock_screen(), layout, model)

    def test_render_nav_bar(self) -> None:
        layout = _computed_layout()
        render_nav_bar(_mock_screen(), layout)

    def test_render_safety_panel(self) -> None:
        layout = _computed_layout()
        render_safety_panel(_mock_screen(), layout, POCSModel())

    def test_render_mount_panel_not_connected(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.mount.connected = False
        render_mount_panel(_mock_screen(), layout, model)

    def test_render_mount_panel_tracking(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.mount.connected = True
        model.mount.is_tracking = True
        render_mount_panel(_mock_screen(), layout, model)

    def test_render_mount_panel_parked(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.mount.connected = True
        model.mount.is_parked = True
        render_mount_panel(_mock_screen(), layout, model)

    def test_render_observation_panel_no_obs(self) -> None:
        layout = _computed_layout()
        render_observation_panel(_mock_screen(), layout, POCSModel())

    def test_render_observation_panel_with_obs(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.scheduler.observing.field_name = "M31"
        model.scheduler.observing.exposure_s = 120.0
        model.scheduler.observing.current_exp_num = 5
        render_observation_panel(_mock_screen(), layout, model)

    def test_render_cameras_panel_no_cameras(self) -> None:
        layout = _computed_layout()
        render_cameras_panel(_mock_screen(), layout, POCSModel())

    def test_render_cameras_panel_with_camera(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        cam = CameraModel(name="cam1")
        cam.connected = True
        cam.is_exposing = True
        cam.temperature = "-10.00"
        cam.filter_name = "L"
        model.cameras.append(cam)
        render_cameras_panel(_mock_screen(), layout, model)

    def test_render_cmdlog_panel(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        layout = _computed_layout()
        log = CmdLog()
        log.push("INFO", "test message")
        render_cmdlog_panel(_mock_screen(), layout, log)

    def test_render_modal_inactive_no_output(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        screen = _mock_screen()
        render_modal(screen, layout, model)
        screen.attron.assert_not_called()

    def test_render_modal_active(self) -> None:
        layout = _computed_layout()
        model = POCSModel()
        model.modal.active = True
        model.modal.prompt = "Are you sure?"
        model.modal.choices = ["Yes", "No"]
        model.modal.selected = 0
        render_modal(_mock_screen(), layout, model)

    def test_render_dashboard(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        layout = _computed_layout()
        render_dashboard(_mock_screen(), layout, POCSModel(), CmdLog())


# ---------------------------------------------------------------------------
# panels.help
# ---------------------------------------------------------------------------


class TestHelpPanel:
    @pytest.fixture(autouse=True)
    def _color(self, patch_color_pair) -> None:
        pass

    def test_render_help(self) -> None:
        layout = _computed_layout()
        render_help(_mock_screen(), layout, POCSModel())

    def test_render_help_small_screen(self) -> None:
        """Render should not crash on a very small terminal."""
        layout = _computed_layout(width=40, height=10)
        render_help(_mock_screen(rows=10, cols=40), layout, POCSModel())


# ---------------------------------------------------------------------------
# panels.operations (rendering)
# ---------------------------------------------------------------------------


class TestOperationsRenderer:
    @pytest.fixture(autouse=True)
    def _color(self, patch_color_pair) -> None:
        pass

    def test_render_operations(self) -> None:
        from panoptes.pocs.tui.cmdlog import CmdLog

        layout = _computed_layout()
        render_operations(_mock_screen(), layout, POCSModel(), 0, CmdLog())

    def test_render_operations_separator_selected(self) -> None:
        """Cursor on a separator row should not crash."""
        from panoptes.pocs.tui.cmdlog import CmdLog
        from panoptes.pocs.tui.panels.operations import MENU_ITEMS

        separator_idx = next(i for i, (_, a) in enumerate(MENU_ITEMS) if a is None)
        layout = _computed_layout()
        render_operations(_mock_screen(), layout, POCSModel(), separator_idx, CmdLog())
