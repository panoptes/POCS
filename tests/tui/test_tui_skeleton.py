from panoptes.pocs.tui import model
from panoptes.pocs.tui.actions import action_abort_exposure, action_park, action_snapshot
from panoptes.pocs.tui.cmdlog import CmdLog
from panoptes.pocs.tui.input import KEY_MAP
from panoptes.pocs.tui.layout import Layout, View, layout_compute
from panoptes.pocs.tui.scanner import Scanner
from panoptes.pocs.tui.theme import SPARK_CHARS, sparkline


def test_model_defaults():
    snapshot = model.POCSModel()
    assert snapshot.scan_count == 0
    assert snapshot.system.state == "unknown"
    assert len(snapshot.cameras) == 0


def test_camera_progress_history_maxlen():
    camera = model.CameraModel()
    assert camera.progress_hist.maxlen == model.SPARKLINE_LEN


def test_cmdlog_push_and_tail():
    cmdlog = CmdLog()
    cmdlog.push("INFO", "one")
    cmdlog.push("WARN", "two")

    entries = cmdlog.tail(1)
    assert len(entries) == 1
    assert entries[0].msg == "two"


def test_sparkline_width():
    out = sparkline([0.0, 0.5, 1.0], width=5)
    assert len(out) == 5
    assert set(out).issubset(set(SPARK_CHARS))


def test_layout_compute_stub_no_throw():
    lay = Layout(width=80, height=24, active_view=View.DASHBOARD)
    layout_compute(lay)


def test_scanner_snapshot_defaults():
    scanner = Scanner(interval_s=0.01)
    scanner.start()
    snapshot = scanner.snapshot()
    scanner.stop()

    assert snapshot.scan_count >= 0


def test_key_map_contains_required_actions():
    assert KEY_MAP[ord("q")] == "quit"
    assert KEY_MAP[ord("p")] == "park"
    assert KEY_MAP[ord("?")] == "help"


def test_action_stubs_log_requests():
    cmdlog = CmdLog()
    action_park(None, cmdlog)
    action_abort_exposure(None, cmdlog)
    action_snapshot(None, cmdlog)

    entries = cmdlog.tail(3)
    assert [entry.level for entry in entries] == ["INFO", "WARN", "INFO"]
