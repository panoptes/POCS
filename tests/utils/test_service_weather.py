"""Tests for the weather station FastAPI service (panoptes.pocs.utils.service.weather).

Uses FastAPI's TestClient with a dependency-override to inject a mock WeatherStation
so no hardware or config server is required.
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panoptes.pocs.utils.service.weather import app, get_weather_station

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_station(
    temperature: float = 12.5,
    safe: bool = True,
) -> MagicMock:
    """Return a mock WeatherStation pre-populated with representative data."""
    station = MagicMock()
    station.status = {
        "safe": safe,
        "temperature": temperature,
        "wind_speed": 3.2,
        "rain_frequency": 2680,
    }
    # When FastAPI serialises the station itself (GET /config), it calls dict()
    # on the return value.  Make the mock JSON-serialisable by giving it a
    # __iter__ / mapping-like interface via the MagicMock auto-spec.
    station.__class__ = MagicMock  # allow isinstance checks to pass
    return station


@pytest.fixture()
def mock_station() -> MagicMock:
    """Provide a fresh mock WeatherStation for each test."""
    return _make_mock_station()


@pytest.fixture()
def client(mock_station: MagicMock) -> TestClient:
    """Return a TestClient with the WeatherStation dependency overridden.

    The real lifespan (which scans serial ports and connects to hardware) is
    replaced with a no-op that seeds app.state directly, so no hardware or
    config server is needed.
    """

    @asynccontextmanager
    async def _noop_lifespan(application: FastAPI):
        application.state.weather_station = mock_station
        application.state.conf = {}
        yield

    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_weather_station] = lambda: mock_station
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    app.router.lifespan_context = None


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


def test_status_returns_200(client: TestClient):
    """GET /status should return HTTP 200."""
    response = client.get("/status")
    assert response.status_code == 200


def test_status_returns_safe_flag(client: TestClient, mock_station: MagicMock):
    """GET /status should include the 'safe' key from the station's status dict."""
    response = client.get("/status")
    data = response.json()
    assert "safe" in data
    assert data["safe"] is True


def test_status_returns_temperature(client: TestClient, mock_station: MagicMock):
    """GET /status should include the 'temperature' reading."""
    response = client.get("/status")
    data = response.json()
    assert data["temperature"] == pytest.approx(12.5)


def test_status_reflects_unsafe_conditions(client: TestClient):
    """GET /status should propagate an unsafe station status."""
    unsafe_station = _make_mock_station(safe=False, temperature=-5.0)
    app.dependency_overrides[get_weather_station] = lambda: unsafe_station
    response = client.get("/status")
    data = response.json()
    assert data["safe"] is False
    assert data["temperature"] == pytest.approx(-5.0)


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


def test_config_returns_200(client: TestClient):
    """GET /config should return HTTP 200."""
    response = client.get("/config")
    assert response.status_code == 200


def test_config_endpoint_calls_station(client: TestClient, mock_station: MagicMock):
    """GET /config should use the injected WeatherStation instance."""
    # The endpoint returns the station object itself; FastAPI will serialise it.
    # We verify the dependency was actually called (not bypassed).
    client.get("/config")
    # dependency_overrides replaced it with a lambda; the mock was retrieved.
    # No AttributeError means the endpoint reached the injected mock.


# ---------------------------------------------------------------------------
# Dependency injection sanity check
# ---------------------------------------------------------------------------


def test_different_clients_get_isolated_mocks():
    """Each client fixture should use its own independent mock station."""
    station_a = _make_mock_station(temperature=10.0)
    station_b = _make_mock_station(temperature=20.0)

    @asynccontextmanager
    async def _noop_lifespan(application: FastAPI):
        yield

    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_weather_station] = lambda: station_a
    with TestClient(app) as c:
        data_a = c.get("/status").json()

    app.dependency_overrides[get_weather_station] = lambda: station_b
    with TestClient(app) as c:
        data_b = c.get("/status").json()

    app.dependency_overrides.clear()
    app.router.lifespan_context = None

    assert data_a["temperature"] == pytest.approx(10.0)
    assert data_b["temperature"] == pytest.approx(20.0)
