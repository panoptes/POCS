"""Tests for the `pocs weather` CLI commands, including the `setup` subcommand."""

import subprocess
from pathlib import Path
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


# ---------------------------------------------------------------------------
# setup — /dev/mount symlink causes that port to be skipped
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_skips_mount_port(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """/dev/ttyUSB0 claimed by /dev/mount is skipped; AAG found on /dev/ttyUSB1."""
    mock_glob.return_value = ["/dev/ttyUSB0", "/dev/ttyUSB1"]
    mock_comports.return_value = [
        _make_port_info("/dev/ttyUSB0"),
        _make_port_info("/dev/ttyUSB1", vid=0x0403, pid=0x6001, serial_number="FT001"),
    ]
    # Only USB1 should be probed; USB0 is the mount.
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    mount_symlink = MagicMock(spec=Path)
    mount_symlink.is_symlink.return_value = True
    mount_symlink.resolve.return_value = Path("/dev/ttyUSB0")

    with (
        patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls,
        patch("panoptes.utils.config.client.set_config"),
    ):
        # Path("/dev/mount") → our mock; Path(device).resolve() uses real Path
        def path_side_effect(arg):
            if arg == "/dev/mount":
                return mount_symlink
            return Path(arg)

        mock_path_cls.side_effect = path_side_effect

        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "skipping" in result.output.lower() or "mount" in result.output.lower()
    # serial.Serial should have been called exactly once (for USB1, not USB0)
    assert mock_serial_cls.call_count == 1
    assert mock_serial_cls.call_args[0][0] == "/dev/ttyUSB1"


# ---------------------------------------------------------------------------
# setup — OSError when resolving /dev/mount is silently ignored
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_mount_symlink_resolve_oserror(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """/dev/mount exists but resolve() raises OSError — probing continues normally."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    broken_symlink = MagicMock(spec=Path)
    broken_symlink.is_symlink.return_value = True
    broken_symlink.resolve.side_effect = OSError("dangling symlink")

    with (
        patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls,
        patch("panoptes.utils.config.client.set_config"),
    ):

        def path_side_effect(arg):
            if arg == "/dev/mount":
                return broken_symlink
            return Path(arg)

        mock_path_cls.side_effect = path_side_effect
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "AAG CloudWatcher detected" in result.output


# ---------------------------------------------------------------------------
# setup — generic Exception in probe loop is caught and port is skipped
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_generic_exception_skipped(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """Generic Exception (not SerialException) during probe is caught; port is skipped."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.side_effect = RuntimeError("unexpected hardware error")

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "unexpected error" in result.output


# ---------------------------------------------------------------------------
# setup — port_info found via resolved path (symlink fallback)
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_port_info_via_resolved_path(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """When comports reports the real path but glob yields a symlink, the port_info
    is found by resolving the found device path."""
    mock_glob.return_value = ["/dev/ttyUSB-sym"]
    # comports reports the resolved (real) path, not the symlink
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB-real")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with (
        patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls,
        patch("panoptes.utils.config.client.set_config"),
    ):

        def path_side_effect(arg):
            if arg == "/dev/mount":
                m = MagicMock(spec=Path)
                m.is_symlink.return_value = False
                return m
            if arg == "/dev/ttyUSB-sym":
                m = MagicMock(spec=Path)
                m.resolve.return_value = Path("/dev/ttyUSB-real")
                return m
            return Path(arg)

        mock_path_cls.side_effect = path_side_effect
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "AAG CloudWatcher detected" in result.output


# ---------------------------------------------------------------------------
# setup — port_info with no description or manufacturer (branch coverage)
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_no_description_no_manufacturer(
    mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner
):
    """When the port has no description or manufacturer the info lines are omitted."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0", description=None, manufacturer=None)]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config"):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "Description" not in result.output
    assert "Manufacturer" not in result.output
    assert 'SYMLINK+="weather"' in result.output


# ---------------------------------------------------------------------------
# setup — sudo tee fails → non-zero exit
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_tee_fails(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """CalledProcessError from sudo tee produces an error message and exits non-zero."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["sudo", "tee", "/etc/udev/rules.d/92-panoptes-weather.rules"], stderr=b"Permission denied"
        )
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "Failed to write" in result.output


# ---------------------------------------------------------------------------
# setup — udevadm reload fails → warning only, exit 0
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_udevadm_reload_fails(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """CalledProcessError from udevadm prints a warning but does not exit non-zero."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")

    tee_ok = MagicMock(returncode=0, stderr=b"")
    udevadm_err = subprocess.CalledProcessError(
        1, ["sudo", "udevadm", "control", "--reload"], stderr="rules directory not found"
    )

    with (
        patch("subprocess.run", side_effect=[tee_ok, udevadm_err]),
        patch("panoptes.utils.config.client.set_config"),
    ):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "failed to reload" in result.output.lower()


# ---------------------------------------------------------------------------
# setup — config server update fails → warning only, exit 0
# ---------------------------------------------------------------------------


@patch("subprocess.run")
@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_config_server_fails(mock_glob, mock_serial_cls, mock_comports, mock_run, cli_runner):
    """Exception from set_config prints a warning but does not exit non-zero."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = [_make_port_info("/dev/ttyUSB0")]
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")
    mock_run.return_value = MagicMock(returncode=0, stderr=b"")

    with patch("panoptes.utils.config.client.set_config", side_effect=ConnectionRefusedError("no server")):
        result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code == 0, result.output
    assert "config server" in result.output.lower() or "serial_port" in result.output.lower()


# ---------------------------------------------------------------------------
# setup — port not in comports and path doesn't resolve differently → VID/PID error
# ---------------------------------------------------------------------------


@patch("panoptes.pocs.utils.cli.weather.serial.tools.list_ports.comports")
@patch("panoptes.pocs.utils.cli.weather.serial.Serial")
@patch("panoptes.pocs.utils.cli.weather._glob.glob")
def test_setup_port_info_not_in_comports_no_symlink(mock_glob, mock_serial_cls, mock_comports, cli_runner):
    """AAG responds but the device isn't in comports and its path doesn't resolve to
    a different string — port_info stays None → vendor/product ID error."""
    mock_glob.return_value = ["/dev/ttyUSB0"]
    mock_comports.return_value = []  # empty — device absent from comports
    mock_serial_cls.return_value = _make_serial_cm(b"!N CloudWatcher  !\x11            0")

    result = cli_runner.invoke(app, ["weather", "setup"])

    assert result.exit_code != 0
    assert "vendor/product ID" in result.output
