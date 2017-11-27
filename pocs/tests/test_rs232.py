import pytest
import serial  # PySerial, from https://github.com/pyserial/pyserial

from pocs.utils import rs232
from pocs.utils.config import load_config

from pocs.tests.serial_handlers import protocol_test


@pytest.fixture(scope="module")
def handler():
    # Install our test handlers for the duration
    serial.protocol_handler_packages.append('pocs.tests.serial_handlers')
    yield True
    # Remove our test handlers
    serial.protocol_handler_packages.remove('pocs.tests.serial_handlers')


def test_basic(handler):
    """  """
    ser = rs232.SerialData(port="test://")
    assert ser.ser
    assert not ser.is_connected


def test_bad_handler(handler):
    """  """
    with pytest.raises(ValueError):
        rs232.SerialData(port="another://")
