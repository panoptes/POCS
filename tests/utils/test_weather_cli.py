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


def _make_port_info(
    device,
    vid=0x067B,
    pid=0x2303,
    serial_number="SN42",
    description="PL2303",
    manufacturer="Prolific",
):
    """Return a mock pyserial ListPortInfo-like object."""
    p = MagicMock()
    p.device = device
    p.vid = vid
    p.pid = pid
    p.serial_number = serial_number
    p.description = description
    p.manufacturer = manufacturer
    return p


# ---------------------------------------------------------------------------
# Helpers to build a mock serial.Serial context manager
# ---------------------------------------------------------------------------


def _make_serial_cm(response: bytes):
    """Return a mock Serial instance (usable as context manager) that returns ``response`` on read()."""
    ser = MagicMock()
    ser.read.return_value = response
    ser.__enter__ = MagicMock(return_value=ser)
    ser.__exit__ = MagicMock(return_value=False)
    return ser


# ---------------------------------------------------------------------------
# setup — AAG device found on first port
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_finds_aag_on_first_port(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """First port responds with !N  → udev rule is written for that port."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config"):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "AAG CloudWatcher detected" in result.output
    assert "92-panoptes-weather.rules" in result.output

    tee_call = next(c for c in mock_run.call_args_list if "tee" in c.args[0])
    rule = tee_call.kwargs["input"].decode()
    assert 'ATTRS{idVendor}=="067b"' in rule
    assert 'ATTRS{idProduct}=="2303"' in rule
    assert 'ATTRS{serial}=="SN42"' in rule
    assert 'SYMLINK+="weather"' in rule


# ---------------------------------------------------------------------------
# setup — first port is not AAG, second port is
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_skips_non_aag_ports(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """Non-responding ports are skipped; the AAG is identified on the second port."""
    mock_glob.return_value = ["/dev/ttyUSB0", "/dev/ttyUSB1"]
    mock_comports.return_value = [
        _make_port_info("/dev/ttyUSB0", serial_number=None),
        _make_port_info("/dev/ttyUSB1", vid=0x0403, pid=0x6001, serial_number="FT001"),
    ]
    # First port returns garbage; second returns valid AAG response.
    mock_serial_cls.side_effect = [
        _make_serial_cm(b"\x00\x00\x00"),
        _make_serial_cm(b"!N CloudWatcher  !\x11            0"),
    ]
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config"):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "AAG CloudWatcher detected" in result.output

    tee_call = next(c for c in mock_run.call_args_list if "tee" in c.args[0])
    rule = tee_call.kwargs["input"].decode()
    assert 'ATTRS{idVendor}=="0403"' in rule
    assert 'ATTRS{serial}=="FT001"' in rule


# ---------------------------------------------------------------------------
# setup — no AAG found on any port
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_no_aag_found(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """If no port responds with an AAG handshake the command exits non-zero."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"\x00" * 30)

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# setup — no matching ports at all
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_no_ports_match_glob(mock_glob, cli_runner):
    """If the glob matches nothing, the command exits non-zero immediately."""
    mock_glob.return_value = []

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "No devices found" in result.output


# ---------------------------------------------------------------------------
# setup — device found but no VID/PID
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_no_vid_pid(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """A port that responds to AAG but has no USB VID/PID exits non-zero."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0", vid=None, pid=None)]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "vendor/product ID" in result.output


# ---------------------------------------------------------------------------
# setup — serial port raises SerialException
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_serial_exception_is_skipped(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """Ports that raise SerialException are skipped gracefully."""
    import serial as _serial

    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.side_effect = _serial.SerialException("Permission denied")

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# setup — udev rule omits serial when serial_number is None
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_rule_omits_serial_when_none(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """When serial_number is None the ATTRS{serial} clause is omitted from the rule."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0", serial_number=None)]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config"):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    tee_call = next(c for c in mock_run.call_args_list if "tee" in c.args[0])
    rule = tee_call.kwargs["input"].decode()
    assert "serial" not in rule
    assert 'SYMLINK+="weather"' in rule
