"""Tests for the CLI main application."""

import pytest
from unittest.mock import MagicMock, patch
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
    # Should suggest using help option (checking for "help" to avoid ANSI color code issues)
    assert "help" in result.output


def test_mount_subcommand_no_args_shows_help(cli_runner):
    """Test that 'pocs mount' with no arguments shows help."""
    result = cli_runner.invoke(app, ["mount"])

    # Should show help for mount subcommand
    assert "Usage:" in result.output
    assert "Commands" in result.output or "Options" in result.output
    # Check for some mount-specific commands
    assert "park" in result.output or "home" in result.output


def test_camera_subcommand_no_args_shows_help(cli_runner):
    """Test that 'pocs camera' with no arguments shows help."""
    result = cli_runner.invoke(app, ["camera"])

    # Should show help for camera subcommand
    assert "Usage:" in result.output
    assert "Commands" in result.output or "Options" in result.output


def test_config_subcommand_no_args_shows_help(cli_runner):
    """Test that 'pocs config' with no arguments shows help."""
    result = cli_runner.invoke(app, ["config"])

    # Should show help for config subcommand
    assert "Usage:" in result.output
    assert "Commands" in result.output or "Options" in result.output


def test_version_command(cli_runner):
    """Test that 'pocs version' shows the version information."""
    result = cli_runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "panoptes-pocs" in result.output
    assert "panoptes-utils" in result.output


def test_update_help_shows_options(cli_runner):
    """Test that 'pocs update --help' documents --branch, --dev options."""
    import re

    result = cli_runner.invoke(app, ["update", "--help"])
    # Strip ANSI escape codes before asserting so colour formatting doesn't break the check.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)

    assert result.exit_code == 0
    assert "--branch" in plain or "-b" in plain
    assert "--dev" in plain


def test_update_invalid_branch_name_rejected(cli_runner):
    """Test that branch names starting with '-' are rejected."""
    result = cli_runner.invoke(app, ["update", "--branch", "--force"])

    assert result.exit_code != 0


@patch("panoptes.pocs.utils.cli.main.find_project_root")
@patch("panoptes.pocs.utils.cli.main.run_uv_command")
@patch("panoptes.pocs.utils.cli.main.Repo")
def test_update_default_uses_latest_tag(mock_repo_cls, mock_uv, mock_root, cli_runner):
    """Test that the default update mode checks out the latest tagged release."""
    mock_root.return_value = "/fake/project"

    # Set up fake tag with a commit.
    fake_commit = MagicMock()
    fake_commit.committed_date = 1000
    fake_tag = MagicMock()
    fake_tag.name = "v1.2.3"
    fake_tag.commit = fake_commit

    # Set up repo mock.
    mock_repo = MagicMock()
    mock_repo.tags = [fake_tag]
    mock_repo.is_dirty.return_value = False
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.head.commit = fake_commit
    mock_repo.git.stash.return_value = ""
    mock_repo_cls.return_value = mock_repo

    result = cli_runner.invoke(app, ["update"])

    # Should have attempted to checkout the latest tag.
    mock_repo.git.checkout.assert_called_once_with("v1.2.3")


@patch("panoptes.pocs.utils.cli.main.find_project_root")
@patch("panoptes.pocs.utils.cli.main.run_uv_command")
@patch("panoptes.pocs.utils.cli.main.Repo")
def test_update_dev_pulls_main(mock_repo_cls, mock_uv, mock_root, cli_runner):
    """Test that --dev pulls the latest commit from main."""
    mock_root.return_value = "/fake/project"

    fake_commit = MagicMock()
    fake_remote_commit = MagicMock()
    tracking = MagicMock()
    tracking.commit = fake_remote_commit

    mock_repo = MagicMock()
    mock_repo.is_dirty.return_value = False
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.active_branch.tracking_branch.return_value = tracking
    mock_repo.head.commit = fake_commit
    mock_repo.git.stash.return_value = ""
    mock_repo.iter_commits.return_value = []
    mock_repo_cls.return_value = mock_repo

    result = cli_runner.invoke(app, ["update", "--dev"])

    # Should pull from 'main'.
    mock_repo.remotes.origin.pull.assert_called_once_with("main")


@patch("panoptes.pocs.utils.cli.main.find_project_root")
@patch("panoptes.pocs.utils.cli.main.run_uv_command")
@patch("panoptes.pocs.utils.cli.main.Repo")
def test_update_branch_option_bypasses_tag(mock_repo_cls, mock_uv, mock_root, cli_runner):
    """Test that --branch pulls from the specified branch, ignoring tags."""
    mock_root.return_value = "/fake/project"

    fake_commit = MagicMock()
    fake_remote_commit = MagicMock()
    tracking = MagicMock()
    tracking.commit = fake_remote_commit

    mock_repo = MagicMock()
    mock_repo.is_dirty.return_value = False
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.active_branch.tracking_branch.return_value = tracking
    mock_repo.head.commit = fake_commit
    mock_repo.git.stash.return_value = ""
    mock_repo.iter_commits.return_value = []
    mock_repo_cls.return_value = mock_repo

    result = cli_runner.invoke(app, ["update", "--branch", "develop"])

    # Should pull from 'develop', not a tag.
    mock_repo.git.checkout.assert_called_once_with("develop")
    mock_repo.remotes.origin.pull.assert_called_once_with("develop")
