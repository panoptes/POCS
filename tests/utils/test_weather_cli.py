"""Tests for the `pocs weather` CLI commands, including the `setup` subcommand."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app


@pytest.fixture
def cli_runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_port(
    device,
    vid=0x0403,
    pid=0x6001,
    serial_number="SN123",
    description="FT232R",
    manufacturer="FTDI",
):
    """Return a mock ListPortInfo-like object."""
    p = MagicMock()
    p.device = device
    p.vid = vid
    p.pid = pid
    p.serial_number = serial_number
    p.description = description
    p.manufacturer = manufacturer
    return p


# ---------------------------------------------------------------------------
# setup — new device detected automatically (no power-cycle flag)
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.time.sleep")
@patch("panoptes.pocs.utils.cli.weather.time.monotonic")
@patch("panoptes.pocs.utils.cli.weather.get_serial_port_info")
def test_setup_detects_new_device(mock_ports, mock_monotonic, mock_sleep, mock_run, cli_runner):
    """A new USB serial port appearing after the prompt writes a udev rule."""
    before_port = _make_port("/dev/ttyUSB0")
    new_port = _make_port("/dev/ttyUSB1", serial_number="WS999")

    # First call (snapshot before): only the pre-existing port.
    # Subsequent calls return both ports so the new one is found immediately.
    mock_ports.side_effect = [
        [before_port],  # snapshot
        [before_port, new_port],  # first poll (finds new device)
        [before_port, new_port],  # re-fetch for port info object
    ]

    # Monotonic advances past a single loop iteration without hitting the deadline.
    mock_monotonic.side_effect = [0.0, 1.0, 2.0, 100.0]

    # All subprocess.run calls succeed.
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    # Patch set_config so we don't need a running config server.
    with patch("panoptes.utils.config.client.set_config"):
        # Supply "y" to the "press Enter once power-cycled" confirmation.
        result = cli_runner.invoke(app, ["weather", "setup"], input="y\n")

    assert result.exit_code == 0, result.output
    assert "/dev/ttyUSB1" in result.output
    assert "92-panoptes-weather.rules" in result.output

    # Verify the udev rule content passed to `sudo tee`.
    tee_call = next(c for c in mock_run.call_args_list if "tee" in c.args[0])
    rule = tee_call.kwargs["input"].decode()
    assert 'ATTRS{idVendor}=="0403"' in rule
    assert 'ATTRS{idProduct}=="6001"' in rule
    assert 'ATTRS{serial}=="WS999"' in rule
    assert 'SYMLINK+="weather"' in rule


# ---------------------------------------------------------------------------
# setup — power-cycle path
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.time.sleep")
@patch("panoptes.pocs.utils.cli.weather.time.monotonic")
@patch("panoptes.pocs.utils.cli.weather.get_serial_port_info")
@patch("panoptes.pocs.utils.cli.weather.requests.post")
def test_setup_power_cycle(mock_post, mock_ports, mock_monotonic, mock_sleep, mock_run, cli_runner):
    """--power-cycle issues power-off / power-on before detection."""
    before_port = _make_port("/dev/ttyUSB0")
    new_port = _make_port("/dev/ttyUSB1", serial_number=None)

    mock_ports.side_effect = [
        [before_port],
        [before_port, new_port],
        [before_port, new_port],
    ]
    mock_monotonic.side_effect = [0.0, 1.0, 2.0, 100.0]

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_post.return_value = mock_resp
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config"):
        result = cli_runner.invoke(
            app,
            ["weather", "setup", "--power-cycle", "--relay", "weather_station"],
        )

    assert result.exit_code == 0, result.output

    # Expect two POST calls: turn_off then turn_on.
    assert mock_post.call_count == 2
    commands = [c.kwargs["json"]["command"] for c in mock_post.call_args_list]
    assert commands == ["turn_off", "turn_on"]

    # Rule should omit the serial attribute when serial_number is None.
    tee_call = next(c for c in mock_run.call_args_list if "tee" in c.args[0])
    rule = tee_call.kwargs["input"].decode()
    assert "serial" not in rule
    assert 'SYMLINK+="weather"' in rule


# ---------------------------------------------------------------------------
# setup — timeout: no new device appears
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.time.sleep")
@patch("panoptes.pocs.utils.cli.weather.time.monotonic")
@patch("panoptes.pocs.utils.cli.weather.get_serial_port_info")
def test_setup_timeout(mock_ports, mock_monotonic, mock_sleep, cli_runner):
    """When no new device appears within the timeout the command exits non-zero."""
    existing_port = _make_port("/dev/ttyUSB0")

    # Always return the same single port.
    mock_ports.return_value = [existing_port]

    # Simulate the deadline being reached on the second monotonic() call.
    mock_monotonic.side_effect = [0.0, 0.5, 999.0]

    result = cli_runner.invoke(app, ["weather", "setup"], input="y\n")

    assert result.exit_code != 0
    assert "No new serial device detected" in result.output


# ---------------------------------------------------------------------------
# setup — no USB VID/PID available
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.time.sleep")
@patch("panoptes.pocs.utils.cli.weather.time.monotonic")
@patch("panoptes.pocs.utils.cli.weather.get_serial_port_info")
def test_setup_no_vid_pid(mock_ports, mock_monotonic, mock_sleep, cli_runner):
    """If the detected device has no VID/PID the command exits non-zero."""
    before_port = _make_port("/dev/ttyUSB0")
    new_port = _make_port("/dev/ttyUSB1", vid=None, pid=None)

    mock_ports.side_effect = [
        [before_port],
        [before_port, new_port],
        [before_port, new_port],
    ]
    mock_monotonic.side_effect = [0.0, 1.0, 100.0]

    result = cli_runner.invoke(app, ["weather", "setup"], input="y\n")

    assert result.exit_code != 0
    assert "vendor/product ID" in result.output
