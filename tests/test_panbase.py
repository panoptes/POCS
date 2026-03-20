from unittest.mock import MagicMock

import pytest

from panoptes.pocs.base import PanBase
from panoptes.pocs.utils.telemetry import PowerReading


@pytest.fixture
def pan_base():
    # Mock the telemetry client to avoid network calls.
    base = PanBase()
    base.telemetry = MagicMock()
    return base


def test_record_telemetry_dict(pan_base):
    data = {"test": "data"}
    pan_base.record_telemetry(data, event_type="test_event")
    pan_base.telemetry.post_event.assert_called_once_with("test_event", data)


def test_record_telemetry_dict_no_type(pan_base):
    data = {"test": "data"}
    pan_base.record_telemetry(data)
    pan_base.telemetry.post_event.assert_called_once_with("unknown", data)


def test_record_telemetry_model(pan_base):
    reading = PowerReading(ac_ok=True, battery_low=False, mount=1.2, fans=0.5, weather_station=0.1)
    # The PowerReading has type="power"
    pan_base.record_telemetry(reading)
    # event_type should be "power" from the model
    pan_base.telemetry.post_event.assert_called_once_with("power", reading.model_dump(mode="json"))


def test_record_telemetry_model_with_override(pan_base):
    reading = PowerReading(ac_ok=True, battery_low=False, mount=1.2, fans=0.5, weather_station=0.1)
    # Pass event_type override
    pan_base.record_telemetry(reading, event_type="overridden")
    # Even with override, currently the code prefers model.type if available.
    # Actually, in my fix:
    # event_type = kwargs.pop("event_type", "unknown")  # "overridden"
    # if hasattr(model, "model_dump"):
    #     event_type = getattr(model, "type", event_type)  # "power" overrides "overridden"

    pan_base.telemetry.post_event.assert_called_once_with("power", reading.model_dump(mode="json"))


def test_record_telemetry_multiple_values_fix(pan_base):
    # This specifically tests the reported bug:
    # TypeError("TelemetryClient.post_event() got multiple values for argument 'event_type'")
    reading = PowerReading(ac_ok=True, battery_low=False, mount=1.2, fans=0.5, weather_station=0.1)
    # This call should not raise TypeError
    pan_base.record_telemetry(reading, event_type="anything")
    # And it should call post_event once.
    assert pan_base.telemetry.post_event.called
