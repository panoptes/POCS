import pytest
import os

from peas.sensors import ArduinoSerialMonitor

pytestmark = pytest.mark.skipif("TRAVIS" in os.environ and os.environ[
                                "TRAVIS"] == "true", reason="Skipping this test on Travis CI.")


@pytest.fixture(scope='module')
def monitor():
    return ArduinoSerialMonitor(auto_detect=True)


def test_create(monitor):
    assert monitor is not None


def test_has_readers(hardware_test, monitor):
    if hardware_test:
        assert len(monitor.serial_readers) > 0
    else:
        assert len(monitor.serial_readers) == 0
