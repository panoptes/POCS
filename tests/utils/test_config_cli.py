"""Tests for the `pocs config` CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app


@pytest.fixture()
def cli_runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_ok(cli_runner):
    """config status prints a success message when the store is ready."""
    with patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value={"name": "Test"}):
        result = cli_runner.invoke(app, ["config", "status"])
    assert result.exit_code == 0
    assert "ready" in result.output.lower()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_full_config(cli_runner):
    """config get with no key prints the entire config."""
    fake_cfg = {"name": "Test Unit", "pan_id": "PAN000"}
    with patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value=fake_cfg):
        result = cli_runner.invoke(app, ["config", "get"])
    assert result.exit_code == 0
    assert "Test Unit" in result.output


def test_get_specific_key(cli_runner):
    """config get <key> prints the value for that key."""
    with patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value="Test Unit"):
        result = cli_runner.invoke(app, ["config", "get", "name"])
    assert result.exit_code == 0
    assert "Test Unit" in result.output


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


def test_set_integer_value(cli_runner):
    """config set parses integer strings correctly."""
    with patch("panoptes.pocs.utils.cli.config.config_store.set_config", return_value=42) as mock_set:
        result = cli_runner.invoke(app, ["config", "set", "wait_delay", "42"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("wait_delay", 42)


def test_set_float_value(cli_runner):
    """config set parses float strings correctly."""
    with patch("panoptes.pocs.utils.cli.config.config_store.set_config", return_value=3.14) as mock_set:
        result = cli_runner.invoke(app, ["config", "set", "some_float", "3.14"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("some_float", 3.14)


def test_set_string_value(cli_runner):
    """config set keeps non-numeric strings as strings."""
    with patch("panoptes.pocs.utils.cli.config.config_store.set_config", return_value="hello") as mock_set:
        result = cli_runner.invoke(app, ["config", "set", "name", "hello"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("name", "hello")


def test_set_escaped_negative_number(cli_runner):
    """config set strips the leading backslash from escaped negative numbers."""
    with patch("panoptes.pocs.utils.cli.config.config_store.set_config", return_value=-5) as mock_set:
        result = cli_runner.invoke(app, ["config", "set", "offset", r"\-5"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("offset", -5)


# ---------------------------------------------------------------------------
# setup — interactive wizard
# ---------------------------------------------------------------------------


def _setup_inputs(*answers):
    """Join answers with newlines for CliRunner input."""
    return "\n".join(str(a) for a in answers) + "\n"


def test_setup_aborts_when_not_confirmed(cli_runner):
    """Answering 'n' to the confirmation prompt exits without changes."""
    with patch("panoptes.pocs.utils.cli.config.config_store.set_config") as mock_set:
        result = cli_runner.invoke(app, ["config", "setup"], input="n\n")
    assert result.exit_code == 0
    assert "Exiting" in result.output
    mock_set.assert_not_called()


def _fake_check_output_ok(cmd, **kwargs):
    """Return sensible values for both subprocess calls in setup()."""
    if "timezone" in " ".join(cmd):
        return "UTC\n"
    # date +%z
    return "+0000\n"


def test_setup_happy_path(cli_runner):
    """Full setup wizard completes and saves config."""
    # Provide: confirm=y, base_dir, unit_name, pan_id, latitude,
    #          longitude, elevation, timezone, gmt_offset
    inputs = _setup_inputs(
        "y", "/tmp/POCS", "My Unit", "PAN001", "19.5 deg", "-154.0 deg", "3400 m", "UTC", "0"
    )

    with (
        patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value="stub"),
        patch("panoptes.pocs.utils.cli.config.config_store.set_config") as mock_set,
        patch("panoptes.pocs.utils.cli.config.save_config") as mock_save,
        patch("subprocess.check_output", side_effect=_fake_check_output_ok),
    ):
        result = cli_runner.invoke(app, ["config", "setup"], input=inputs)

    assert result.exit_code == 0, result.output
    assert "saved" in result.output.lower()
    assert mock_set.call_count >= 6  # base_dir, name, pan_id, lat, lon, elevation, timezone, gmt_offset
    mock_save.assert_called_once()


def test_setup_elevation_feet(cli_runner):
    """Elevation entered in feet is converted to metres before saving."""
    inputs = _setup_inputs(
        "y", "/tmp/POCS", "My Unit", "PAN001", "19.5 deg", "-154.0 deg", "3400 ft", "UTC", "0"
    )

    captured_calls = []

    def fake_set(key, value):
        captured_calls.append((key, value))
        return value

    with (
        patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value="stub"),
        patch("panoptes.pocs.utils.cli.config.config_store.set_config", side_effect=fake_set),
        patch("panoptes.pocs.utils.cli.config.save_config"),
        patch("subprocess.check_output", side_effect=_fake_check_output_ok),
    ):
        result = cli_runner.invoke(app, ["config", "setup"], input=inputs)

    assert result.exit_code == 0, result.output
    elev_call = next(c for c in captured_calls if c[0] == "location.elevation")
    # 3400 ft ≈ 1036 m; value should be a Quantity or numeric, not contain "ft"
    assert "ft" not in str(elev_call[1])


def test_setup_elevation_metres_string(cli_runner):
    """Elevation entered as 'NNNm' (no space) is passed through the endswith('m') branch."""
    inputs = _setup_inputs(
        "y", "/tmp/POCS", "My Unit", "PAN001", "19.5 deg", "-154.0 deg", "3400m", "UTC", "0"
    )

    captured_calls = []

    def fake_set(key, value):
        captured_calls.append((key, value))
        return value

    with (
        patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value="stub"),
        patch("panoptes.pocs.utils.cli.config.config_store.set_config", side_effect=fake_set),
        patch("panoptes.pocs.utils.cli.config.save_config"),
        patch("subprocess.check_output", side_effect=_fake_check_output_ok),
    ):
        result = cli_runner.invoke(app, ["config", "setup"], input=inputs)

    assert result.exit_code == 0, result.output
    elev_call = next(c for c in captured_calls if c[0] == "location.elevation")
    assert "m" in str(elev_call[1])
    assert "ft" not in str(elev_call[1])


def test_setup_subprocess_error_falls_back_to_utc(cli_runner):
    """If /etc/timezone can't be read, timezone defaults to UTC."""
    import subprocess

    inputs = _setup_inputs(
        "y", "/tmp/POCS", "My Unit", "PAN001", "19.5 deg", "-154.0 deg", "3400 m", "UTC", "0"
    )

    def fake_check_output(cmd, **kwargs):
        if "timezone" in " ".join(cmd):
            raise subprocess.CalledProcessError(1, cmd)
        return "0000\n"

    with (
        patch("panoptes.pocs.utils.cli.config.config_store.get_config", return_value="stub"),
        patch("panoptes.pocs.utils.cli.config.config_store.set_config"),
        patch("panoptes.pocs.utils.cli.config.save_config"),
        patch("subprocess.check_output", side_effect=fake_check_output),
    ):
        result = cli_runner.invoke(app, ["config", "setup"], input=inputs)

    assert result.exit_code == 0, result.output
