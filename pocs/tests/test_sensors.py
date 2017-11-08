import pytest

from peas.sensors import ArduinoSerialMonitor


@pytest.fixture(scope='module')
def monitor():
    return ArduinoSerialMonitor(auto_detect=True)


def test_create(monitor):
    assert monitor is not None


@pytest.mark.hardware
def test_has_readers(monitor):
    assert len(monitor.serial_readers) > 0
