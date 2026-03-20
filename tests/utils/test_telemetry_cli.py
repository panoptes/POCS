from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app
from panoptes.pocs.utils.cli.telemetry import (
    ImageDisplay,
    PowerDisplay,
    SafetyDisplay,
    StatusDisplay,
    TelemetryDisplay,
    WeatherDisplay,
)


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_telemetry_no_args_shows_help(cli_runner):
    result = cli_runner.invoke(app, ["telemetry"])
    assert result.exit_code != 0
    assert "Usage:" in result.output
    assert "tui" in result.output
    assert "run" in result.output
    assert "stop" in result.output
    assert "current" in result.output


def test_telemetry_help_flag(cli_runner):
    result = cli_runner.invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


@patch("subprocess.run")
def test_telemetry_run(mock_run, cli_runner):
    result = cli_runner.invoke(app, ["telemetry", "run", "--host", "1.2.3.4", "--port", "1234", "--verbose"])
    assert result.exit_code == 0
    expected_cmd = [
        "panoptes-utils",
        "telemetry",
        "run",
        "--host",
        "1.2.3.4",
        "--port",
        "1234",
        "--site-dir",
        "telemetry",
        "--verbose",
    ]
    mock_run.assert_called_once_with(expected_cmd)


@patch("subprocess.run")
def test_telemetry_stop(mock_run, cli_runner):
    result = cli_runner.invoke(app, ["telemetry", "stop", "--port", "9999"])
    assert result.exit_code == 0
    expected_cmd = ["panoptes-utils", "telemetry", "stop", "--host", "localhost", "--port", "9999"]
    mock_run.assert_called_once_with(expected_cmd)


@patch("subprocess.run")
def test_telemetry_current(mock_run, cli_runner):
    result = cli_runner.invoke(app, ["telemetry", "current"])
    assert result.exit_code == 0
    expected_cmd = ["panoptes-utils", "telemetry", "current", "--host", "localhost", "--port", "6562"]
    mock_run.assert_called_once_with(expected_cmd)


@patch("panoptes.pocs.utils.cli.telemetry.run_tui")
def test_telemetry_tui_command(mock_run_tui, cli_runner):
    result = cli_runner.invoke(app, ["telemetry", "tui", "--port", "8888"])
    assert result.exit_code == 0
    mock_run_tui.assert_called_once_with(host="localhost", port=8888)


def test_telemetry_display_get_val():
    data = {"a": 1, "b": None}
    assert TelemetryDisplay.get_val(data, "a") == 1
    assert TelemetryDisplay.get_val(data, "b") == 0.0
    assert TelemetryDisplay.get_val(data, "c") == 0.0
    assert TelemetryDisplay.get_val(data, "c", default="N/A") == "N/A"


def test_telemetry_display_get_footer():
    display = TelemetryDisplay()

    # Test missing timestamp
    assert display.get_footer(None) == ""

    # Test valid timestamp
    now = datetime.now(UTC)
    ts = now.isoformat().replace("+00:00", "Z")
    footer = display.get_footer(ts)
    assert "Updated" in footer
    assert "ago" in footer

    # Test some time ago
    ts_past = (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    footer_past = display.get_footer(ts_past)
    assert "30 seconds ago" in footer_past

    # Test invalid timestamp fallback
    assert display.get_footer("not-a-timestamp") == "Updated not-a-timestamp"


def test_weather_display_update():
    display = WeatherDisplay()
    data = {
        "is_safe": True,
        "ambient_temp": 20.5,
        "sky_temp": -10.2,
        "wind_speed": 5.0,
        "cloud_condition": "Clear",
        "rain_condition": "Dry",
    }
    # We can't easily check the output of self.update() in unit test without mocking it,
    # but we can check if it runs without error.
    with patch.object(display, "update") as mock_update:
        display.update_data(data, timestamp="2026-03-19T12:00:00Z")
        assert mock_update.called


def test_power_display_update():
    display = PowerDisplay()
    data = {"ac_ok": True, "battery_low": False, "mount": 1.2, "fans": 0.5, "weather_station": 0.1}
    with patch.object(display, "update") as mock_update:
        display.update_data(data)
        assert mock_update.called


def test_safety_display_update():
    display = SafetyDisplay()
    data = {
        "ac_power": True,
        "is_dark": True,
        "good_weather": True,
        "free_space_root": True,
        "free_space_images": True,
    }
    with patch.object(display, "update") as mock_update:
        display.update_data(data)
        assert mock_update.called


def test_status_display_update():
    display = StatusDisplay()
    data = {
        "state": "observing",
        "next_state": "analyzing",
        "mount_state": "tracking",
        "mount_ra": 150.0,
        "mount_dec": 45.0,
        "is_parked": False,
        "sun_alt": -20.0,
        "moon_alt": 10.0,
    }
    with patch.object(display, "update") as mock_update:
        display.update_data(data)
        assert mock_update.called


def test_image_display_update():
    display = ImageDisplay()
    data = {
        "field_name": "M42",
        "camera_name": "Cam01",
        "exptime": 60.0,
        "filter": "R",
        "start_time": "2026-03-19T12:00:00Z",
        "airmass": 1.2,
    }
    with patch.object(display, "update") as mock_update:
        display.update_data(data)
        assert mock_update.called


def test_weather_display_update_no_data():
    display = WeatherDisplay()
    with patch.object(display, "update") as mock_update:
        display.update_data({})
        assert mock_update.called
        assert "No weather data" in mock_update.call_args[0][0]


def test_power_display_update_no_data():
    display = PowerDisplay()
    with patch.object(display, "update") as mock_update:
        display.update_data({})
        assert mock_update.called
        assert "No power data" in mock_update.call_args[0][0]


def test_safety_display_update_no_data():
    display = SafetyDisplay()
    with patch.object(display, "update") as mock_update:
        display.update_data({})
        assert mock_update.called
        assert "No safety data" in mock_update.call_args[0][0]


def test_status_display_update_no_data():
    display = StatusDisplay()
    with patch.object(display, "update") as mock_update:
        display.update_data({})
        assert mock_update.called
        assert "No status data" in mock_update.call_args[0][0]


def test_image_display_update_no_data():
    display = ImageDisplay()
    with patch.object(display, "update") as mock_update:
        display.update_data({})
        assert mock_update.called
        assert "No image data" in mock_update.call_args[0][0]


@pytest.mark.asyncio
async def test_telemetry_app_update_exception():
    from panoptes.pocs.utils.cli.telemetry import TelemetryApp

    app = TelemetryApp()
    app.client = MagicMock()
    app.client.current.side_effect = Exception("Test Error")

    with patch.object(app, "notify") as mock_notify:
        app.update_telemetry()
        assert mock_notify.called
        assert "Error fetching telemetry" in mock_notify.call_args[0][0]


@pytest.mark.asyncio
async def test_telemetry_app_refresh():
    from panoptes.pocs.utils.cli.telemetry import TelemetryApp

    app = TelemetryApp()
    with patch.object(app, "update_telemetry") as mock_update:
        app.action_refresh()
        assert mock_update.called


@pytest.mark.asyncio
async def test_telemetry_app_update_success():
    from panoptes.pocs.utils.cli.telemetry import TelemetryApp

    app = TelemetryApp()
    app.client = MagicMock()
    app.client.current.return_value = {
        "weather": {"data": {"is_safe": True}, "ts": "2026-03-19T12:00:00Z"},
        "power": {"data": {"ac_ok": True}, "ts": "2026-03-19T12:00:00Z"},
        "safety": {"data": {"ac_power": True}, "ts": "2026-03-19T12:00:00Z"},
        "status": {"data": {"state": "ready"}, "ts": "2026-03-19T12:00:00Z"},
        "images": {"data": {"field_name": "M42"}, "ts": "2026-03-19T12:00:00Z"},
    }

    # Textual compose happens during run, but we can mock query_one
    with patch.object(app, "query_one") as mock_query:
        mock_widget = MagicMock()
        mock_query.return_value = mock_widget
        app.update_telemetry()
        assert mock_query.called
        assert mock_widget.update_data.called


@pytest.mark.asyncio
async def test_telemetry_app_integration():
    from panoptes.pocs.utils.cli.telemetry import TelemetryApp

    app = TelemetryApp()
    # We need to mock the client because it makes a request on mount
    app.client = MagicMock()
    app.client.current.return_value = {"current": {}}

    async with app.run_test() as pilot:
        assert app.query_one("#weather")
        assert app.query_one("#power")
        assert app.query_one("#safety")
        assert app.query_one("#status")
        assert app.query_one("#image")
        await pilot.press("q")


@patch("panoptes.pocs.utils.cli.telemetry.TelemetryApp")
def test_run_tui(mock_app_class):
    from panoptes.pocs.utils.cli.telemetry import run_tui

    mock_app = MagicMock()
    mock_app_class.return_value = mock_app
    run_tui(host="1.2.3.4", port=1234)
    mock_app_class.assert_called_once_with(host="1.2.3.4", port=1234)
    assert mock_app.run.called
