# Test sensors.py ability to read from two sensor boards.

import pytest
import serial

from pocs.utils import rs232


@pytest.fixture(scope='function')
def serial_handlers():
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.insert(0, 'serial_handlers')
    yield True
    # Remove our test handlers.
    serial.protocol_handler_packages.remove('serial_handlers')


# --------------------------------------------------------------------------------------------------
# Basic tests of FakeArduinoSerialHandler.

def test_create(serial_handlers):
    ser = rs232.SerialData(port='arduinosimulator://')
    assert ser.is_connected is True
    ser.disconnect()
    assert ser.is_connected is False


def test_camera_simulator(serial_handlers):
    ser = rs232.SerialData(port='arduinosimulator://?board=camera', baudrate=9600)
    assert ser.is_connected is True
    ser.disconnect()
    assert ser.is_connected is False
    ser.connect()
    assert ser.is_connected is True
    # First read will typically get a fragment of a line, but then the next will
    # get a full line.
    s = ser.read()
    assert s.endswith('\n')
    s = ser.read()
    assert s.startswith('{')
    assert s.endswith('}\r\n')
    assert 'camera_board' in s
    ser.disconnect()
    assert ser.is_connected is False


def test_create_telemetry(serial_handlers):
    ser = rs232.SerialData(port='arduinosimulator://?board=telemetry', baudrate=9600)
    assert ser.is_connected is True
    (ts, reading) = ser.get_and_parse_reading(retry_limit=2)
    assert isinstance(reading, dict)
    assert reading['name'] == 'telemetry_board'
    report_num = reading['report_num']
    assert 1 <= report_num
    assert report_num <= 2
    ser.disconnect()
    assert ser.is_connected is False
