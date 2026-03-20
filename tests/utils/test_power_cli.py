from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app


@pytest.fixture
def cli_runner():
    return CliRunner()


@patch("requests.post")
def test_power_on(mock_post, cli_runner):
    # Mock response
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"relay": "fans", "command": "turn_on"}
    mock_post.return_value = mock_response

    result = cli_runner.invoke(app, ["power", "on", "fans"])

    assert result.exit_code == 0
    assert "{'relay': 'fans', 'command': 'turn_on'}" in result.output

    # Verify that requests.post was called with json=... (the fix)
    # The RelayCommand model dump will have 'relay' and 'command' keys.
    # 'command' will be the string value of the enum.
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "json" in kwargs
    assert kwargs["json"] == {"relay": "fans", "command": "turn_on"}


@patch("requests.post")
def test_power_off(mock_post, cli_runner):
    # Mock response
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"relay": "fans", "command": "turn_off"}
    mock_post.return_value = mock_response

    result = cli_runner.invoke(app, ["power", "off", "fans"])

    assert result.exit_code == 0
    assert "{'relay': 'fans', 'command': 'turn_off'}" in result.output

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "json" in kwargs
    assert kwargs["json"] == {"relay": "fans", "command": "turn_off"}


@patch("requests.get")
def test_power_status(mock_get, cli_runner):
    # Mock response
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "RELAY_0": {"label": "fans", "state": "OFF"},
        "RELAY_1": {"label": "mount", "state": "ON"},
    }
    mock_get.return_value = mock_response

    result = cli_runner.invoke(app, ["power", "status"])

    assert result.exit_code == 0
    assert "fans" in result.output
    assert "OFF" in result.output
    assert "mount" in result.output
    assert "ON" in result.output
