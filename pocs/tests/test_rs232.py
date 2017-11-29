import pytest
import serial  # PySerial, from https://github.com/pyserial/pyserial

from pocs.utils import rs232
from pocs.utils.config import load_config

from pocs.tests.serial_handlers import protocol_buffers
from pocs.tests.serial_handlers import protocol_no_op
from pocs.tests.serial_handlers import protocol_test

THE_HOOKS = None


def create_hooks(ser, *args, **kwargs):
    THE_HOOKS = SimpleSerialHooks(ser)


@pytest.fixture(scope='function')
def handler():
    # Install our test handlers for the duration
    serial.protocol_handler_packages.append('pocs.tests.serial_handlers')
    yield True
    # Remove our test handlers
    serial.protocol_handler_packages.remove('pocs.tests.serial_handlers')


def test_basic(handler):
    # Confirm we can create the SerialData object.
    ser = rs232.SerialData(port='no_op://', open_delay=0)
    # Peek inside, it should have a PySerial instance as member ser.
    assert ser.ser
    assert ser.ser.__class__.__name__ == 'NoOpSerial'
    print(str(ser.ser))
    # Open is automatically called by SerialData.
    assert ser.is_connected
    # Not using threading.
    assert not ser.is_listening

    # no_op handler doesn't do any reading or writing.
    assert '' == ser.read(retry_delay=0.01, retry_limit=2)
    assert 0 == ser.write('')

    ser.disconnect()
    assert not ser.is_connected
    assert not ser.is_listening


def test_without_handler():
    """If the handlers aren't installed, it should fail."""
    with pytest.raises(ValueError):
        rs232.SerialData(port='no_op://')


def test_another_handler(handler):
    """And even when installed, the wrong name won't work."""
    with pytest.raises(ValueError):
        rs232.SerialData(port='bogus://')


def test_unthreaded_io(handler):
    pytest.set_trace()
    protocol_buffers.ResetBuffers(b'abc\r\n')
    ser = rs232.SerialData(port='buffers://', open_delay=0)
    assert ser
    # Peek inside, it should have a PySerial instance as member ser.
    assert ser.ser
    assert ser.ser.__class__.__name__ == 'BuffersSerial'
    print(str(ser.ser))
    # Open is automatically called by SerialData.
    assert ser.is_connected
    # Not using threading.
    assert not ser.is_listening

    # no_op handler doesn't do any reading or writing.
    assert 'abc' == ser.read(retry_delay=0.01, retry_limit=2)
    assert 5 == ser.write(b'def\r\n')

    ser.disconnect()
    assert not ser.is_connected
    assert not ser.is_listening

