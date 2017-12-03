import pytest

from peas.sensors import ArduinoSerialMonitor


@pytest.mark.skip(reason="Can't run without hardware")
@pytest.fixture(scope='module')
def monitor():
    return ArduinoSerialMonitor(auto_detect=True)


@pytest.mark.skip(reason="Can't run without hardware")
def test_create(monitor):
    assert monitor is not None


@pytest.mark.skip(reason="Can't run without hardware")
def test_has_readers(monitor):
    assert len(monitor.serial_readers) > 0
