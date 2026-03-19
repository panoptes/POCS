"""Tests for the power board FastAPI service (panoptes.pocs.utils.service.power).

Uses FastAPI's TestClient with a dependency-override to inject a mock PowerBoard
so no hardware or config server is required.
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panoptes.pocs.utils.service.power import RelayAction, RelayCommand, app, get_power_board

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_relay(label: str, name: str = "RELAY_0", state_name: str = "ON") -> MagicMock:
    """Return a mock Relay with the minimum attributes used by the service."""
    relay = MagicMock()
    relay.name = name
    relay.label = label
    relay.state.name = state_name
    return relay


def _make_mock_board(
    relay_label: str = "mount",
    relay_name: str = "RELAY_0",
    state_name: str = "ON",
) -> MagicMock:
    """Return a mock PowerBoard pre-wired with one relay."""
    board = MagicMock()
    relay = _make_mock_relay(label=relay_label, name=relay_name, state_name=state_name)

    board.relays = [relay]
    board.relay_labels = {relay_label: relay}
    board.status = {
        relay_name: {"label": relay_label, "state": state_name, "reading": 100},
        "ac_ok": True,
        "battery_low": False,
    }
    board.to_dataframe.return_value = pd.DataFrame(
        {relay_label: [100, 110]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    return board


@pytest.fixture()
def mock_board() -> MagicMock:
    """Provide a fresh mock PowerBoard for each test."""
    return _make_mock_board()


@pytest.fixture()
def client(mock_board: MagicMock) -> TestClient:
    """Return a TestClient with the PowerBoard dependency overridden.

    The real lifespan (which instantiates hardware) is replaced with a no-op
    that seeds app.state directly, so no hardware or config server is needed.
    """

    @asynccontextmanager
    async def _noop_lifespan(application: FastAPI):
        application.state.power_board = mock_board
        application.state.conf = {}
        yield

    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_power_board] = lambda: mock_board
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    app.router.lifespan_context = None


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


def test_root_returns_status(client: TestClient, mock_board: MagicMock):
    """GET / should return the power board status dict."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "RELAY_0" in data
    assert data["ac_ok"] is True
    assert data["battery_low"] is False


# ---------------------------------------------------------------------------
# GET /readings
# ---------------------------------------------------------------------------


def test_readings_returns_dataframe_dict(client: TestClient, mock_board: MagicMock):
    """GET /readings should return the dataframe as a nested dict."""
    response = client.get("/readings")
    assert response.status_code == 200
    data = response.json()
    # The dataframe column (relay label) should be present.
    assert "mount" in data
    mock_board.to_dataframe.assert_called_once()


# ---------------------------------------------------------------------------
# POST /control
# ---------------------------------------------------------------------------


def test_control_relay_post_turn_on(client: TestClient, mock_board: MagicMock):
    """POST /control should call turn_on on the correct relay and echo the command."""
    payload = {"relay": "mount", "command": "turn_on"}
    response = client.post("/control", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["relay"] == "mount"
    assert data["command"] == "turn_on"
    mock_board.relay_labels["mount"].turn_on.assert_called_once()


def test_control_relay_post_turn_off(client: TestClient, mock_board: MagicMock):
    """POST /control should call turn_off on the correct relay."""
    payload = {"relay": "mount", "command": "turn_off"}
    response = client.post("/control", json=payload)
    assert response.status_code == 200
    mock_board.relay_labels["mount"].turn_off.assert_called_once()


def test_control_relay_post_by_index(client: TestClient, mock_board: MagicMock):
    """POST /control with an integer relay index should fall back to relays list."""
    # relay_labels lookup raises KeyError for "0", so it falls back to relays[0]
    mock_board.relay_labels = {}  # force the KeyError path
    payload = {"relay": "0", "command": "turn_on"}
    response = client.post("/control", json=payload)
    assert response.status_code == 200
    mock_board.relays[0].turn_on.assert_called_once()


def test_control_relay_invalid_command_returns_422(client: TestClient):
    """POST /control with an unrecognised command should return HTTP 422."""
    payload = {"relay": "mount", "command": "explode"}
    response = client.post("/control", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /relay/{relay}/control/{command}
# ---------------------------------------------------------------------------


def test_control_relay_url_turn_on(client: TestClient, mock_board: MagicMock):
    """GET /relay/{relay}/control/{command} should route to the correct relay."""
    response = client.get("/relay/mount/control/turn_on")
    assert response.status_code == 200
    data = response.json()
    assert data["relay"] == "mount"
    assert data["command"] == "turn_on"
    mock_board.relay_labels["mount"].turn_on.assert_called_once()


def test_control_relay_url_invalid_command_returns_422(client: TestClient, mock_board: MagicMock):
    """GET /relay/.../control/bad should return HTTP 422 for an unrecognised command."""
    response = client.get("/relay/mount/control/bad_command")
    assert response.status_code == 422
    assert "bad_command" in response.json()["detail"]


# ---------------------------------------------------------------------------
# RelayAction enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", list(RelayAction))
def test_relay_action_values_are_strings(action: RelayAction):
    """Each RelayAction member should be a plain string equal to its name."""
    assert isinstance(action, str)
    assert str(action) == action.value


# ---------------------------------------------------------------------------
# RelayCommand model
# ---------------------------------------------------------------------------


def test_relay_command_model_valid():
    """RelayCommand should accept a string relay and a valid RelayAction."""
    cmd = RelayCommand(relay="mount", command=RelayAction.turn_on)
    assert cmd.relay == "mount"
    assert cmd.command is RelayAction.turn_on


def test_relay_command_model_int_relay():
    """RelayCommand should accept an integer relay index."""
    cmd = RelayCommand(relay=0, command=RelayAction.turn_off)
    assert cmd.relay == 0
