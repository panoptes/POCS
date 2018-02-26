# Test sensors.py ability to read from two sensor boards.

import collections
import pytest
import serial

from peas import sensors as sensors_module
from pocs.utils import rs232

SerDevInfo = collections.namedtuple('SerDevInfo', 'device description')


@pytest.fixture(scope='function')
def serial_handlers():
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.insert(0, 'pocs.serial_handlers')
    yield True
    # Remove our test handlers.
    serial.protocol_handler_packages.remove('pocs.serial_handlers')


def list_comports():
    return [
        SerDevInfo(device='bogus://', description='Not an arduino'),
        SerDevInfo(device='loop://', description='Some Arduino device'),
        SerDevInfo(
            device='arduinosimulator://?board=telemetry&name=t1',
            description='Some Arduino device'),
        SerDevInfo(device='arduinosimulator://?board=camera&name=c1', description='Arduino Micro'),
    ]


@pytest.fixture(scope='function')
def inject_list_comports():
    saved = sensors_module.list_comports
    sensors_module.list_comports = list_comports
    yield True
    sensors_module.list_comports = saved


# --------------------------------------------------------------------------------------------------
# Basic tests of FakeArduinoSerialHandler.


def test_create_camera_simulator(serial_handlers):
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


def test_create_default_simulator(serial_handlers):
    """Defaults to creating telemetry_board messages."""
    ser = rs232.SerialData(port='arduinosimulator://', baudrate=9600)
    assert ser.is_connected is True
    (ts, reading) = ser.get_and_parse_reading(retry_limit=2)
    assert isinstance(reading, dict)
    assert reading['name'] == 'telemetry_board'
    report_num = reading['report_num']
    assert 1 <= report_num
    assert report_num <= 2
    ser.disconnect()
    assert ser.is_connected is False


# --------------------------------------------------------------------------------------------------


def test_detect_board_on_port_not_a_board():
    """detect_board_on_port will fail if the port doesn't produce the expected output.

    Detection will fail because loop:// handler doesn't print anything.
    """
    assert sensors_module.detect_board_on_port('loop://') is None


def test_detect_board_on_port_no_handler_installed():
    """Can't find our simulator, so returns None.

    This test doesn't have `serial_handlers` as a param, so the arduinosimulator can't be found by
    PySerial's `serial_for_url`. Therefore, detect_board_on_port won't be able to determine the
    type of board.
    """
    assert sensors_module.detect_board_on_port('arduinosimulator://?board=telemetry') is None


def test_detect_board_on_port_telemetry(serial_handlers):
    """Detect a telemetry board."""
    v = sensors_module.detect_board_on_port('arduinosimulator://?board=telemetry')
    assert isinstance(v, tuple)
    assert v[0] == 'telemetry_board'
    assert isinstance(v[1], rs232.SerialData)
    assert v[1].is_connected is True
    v[1].disconnect()
    assert v[1].is_connected is False


# --------------------------------------------------------------------------------------------------


def test_find_arduino_devices(inject_list_comports):
    v = sensors_module.find_arduino_devices()
    assert len(v) == 3
    assert v == [
        'loop://',
        'arduinosimulator://?board=telemetry&name=t1',
        'arduinosimulator://?board=camera&name=c1',
    ]


# --------------------------------------------------------------------------------------------------


def test_auto_detect_arduino_devices(inject_list_comports, serial_handlers):
    v = sensors_module.auto_detect_arduino_devices()
    assert len(v) == 2
    for ndx, (board, name) in enumerate([('telemetry', 't1'), ('camera', 'c1')]):
        print('ndx=%r   board=%r   name=%r' % (ndx, board, name))
        expected = 'arduinosimulator://?board=%s&name=%s' % (board, name)
        assert v[ndx][0] == '{}_board'.format(board)
        assert isinstance(v[ndx][1], rs232.SerialData)
        assert v[ndx][1].name == expected
        assert v[ndx][1].ser.port == expected
        # ser.name is set by the simulator, a way to test that the correcct
        # simulator setup is in use.
        assert v[ndx][1].ser.name == name
        assert v[ndx][1].is_connected is True
        v[ndx][1].disconnect()
        assert v[ndx][1].is_connected is False
