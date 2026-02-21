"""Tests for the CLI main application."""

import pytest
from typer.testing import CliRunner

# Import will fail if dependencies are not available, so we'll mark the test as optional
pytest.importorskip("panoptes.utils")

from panoptes.pocs.utils.cli.main import app


@pytest.fixture
def cli_runner():
    """Provide a CLI runner for testing."""
    return CliRunner()


def test_no_args_shows_help(cli_runner):
    """Test that running the CLI with no arguments shows the help screen."""
    result = cli_runner.invoke(app, [])

    # With no_args_is_help=True, the help screen is shown
    assert "Usage:" in result.output
    assert "Options" in result.output
    assert "Commands" in result.output
    # Check that some of the expected subcommands are listed
    assert "config" in result.output
    assert "mount" in result.output
    assert "camera" in result.output


def test_help_flag_shows_help(cli_runner):
    """Test that --help flag shows the help screen."""
    result = cli_runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Options" in result.output
    assert "Commands" in result.output


def test_invalid_command_shows_error(cli_runner):
    """Test that an invalid command shows an error message."""
    result = cli_runner.invoke(app, ["invalid-command"])

    assert result.exit_code == 2
    assert "No such command" in result.output
    # Should suggest using help option
    assert "--help" in result.output
