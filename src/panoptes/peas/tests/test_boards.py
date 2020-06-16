import pytest

from panoptes.utils import error
from panoptes.peas.sensors import ArduinoSerialMonitor


@pytest.mark.with_sensors
@pytest.fixture(scope='module')
def monitor():
    return ArduinoSerialMonitor(auto_detect=True)


@pytest.mark.with_sensors
def test_create(monitor):
    assert monitor is not None


@pytest.mark.with_sensors
def test_has_readers(monitor):
    assert len(monitor.serial_readers) > 0


@pytest.mark.without_sensors
def test_bad_autodetect():
    # Will fail if no connections
    with pytest.raises(error.BadSerialConnection):
        ArduinoSerialMonitor(auto_detect=True)


def test_bad_sensor_name():
    with pytest.raises(error.BadSerialConnection):
        ArduinoSerialMonitor(sensor_name='foobar', db_type='memory')
