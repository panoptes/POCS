# Test sensors.py ability to read from two sensor boards.

import collections
import pytest
import queue as queue_module
import serial
import time

from pocs.sensors import arduino_io
from pocs.utils import rs232

# For serial_handlers to be loaded
# import pocs.serial_handlers as serial_handlers_module

SerDevInfo = collections.namedtuple('SerDevInfo', 'device description manufacturer')


@pytest.fixture(scope='function')
def serial_handlers():
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.insert(0, 'pocs.serial_handlers')
    yield True
    # Remove our test handlers.
    serial.protocol_handler_packages.remove('pocs.serial_handlers')


def get_serial_port_info():
    return [
        SerDevInfo(
            device='bogus://', description='Some USB-to-Serial device', manufacturer='Acme'),
        SerDevInfo(device='loop://', description='Some text', manufacturer='Arduino LLC'),
        SerDevInfo(
            device='arduinosimulator://?board=telemetry&name=t1',
            description='Some Arduino device',
            manufacturer='www.arduino.cc'),
        SerDevInfo(
            device='arduinosimulator://?board=camera&name=c1',
            description='Arduino Micro',
            manufacturer=''),
    ]


@pytest.fixture(scope='function')
def inject_get_serial_port_info():
    saved = rs232.get_serial_port_info
    rs232.get_serial_port_info = get_serial_port_info
    yield True
    rs232.get_serial_port_info = saved


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
    assert arduino_io.detect_board_on_port('loop://') is None


def test_detect_board_on_port_no_handler_installed():
    """Can't find our simulator, so returns None.

    This test doesn't have `serial_handlers` as a param, so the arduinosimulator can't be found by
    PySerial's `serial_for_url`. Therefore, detect_board_on_port won't be able to determine the
    type of board.
    """
    assert arduino_io.detect_board_on_port('arduinosimulator://?board=telemetry') is None


def test_detect_board_on_port_telemetry(serial_handlers):
    """Detect a telemetry board."""
    assert arduino_io.detect_board_on_port(
        'arduinosimulator://?board=telemetry') == 'telemetry_board'


# --------------------------------------------------------------------------------------------------


def test_get_arduino_ports(inject_get_serial_port_info):
    v = arduino_io.get_arduino_ports()
    assert len(v) == 3
    assert v == [
        'loop://',
        'arduinosimulator://?board=telemetry&name=t1',
        'arduinosimulator://?board=camera&name=c1',
    ]


# --------------------------------------------------------------------------------------------------


def test_auto_detect_arduino_devices(inject_get_serial_port_info, serial_handlers):
    v = arduino_io.auto_detect_arduino_devices()
    assert len(v) == 2
    for ndx, (board, name) in enumerate([('telemetry', 't1'), ('camera', 'c1')]):
        print('ndx=%r   board=%r   name=%r' % (ndx, board, name))
        expected = 'arduinosimulator://?board=%s&name=%s' % (board, name)
        assert v[ndx][0] == '{}_board'.format(board)
        assert v[ndx][1] == expected


# --------------------------------------------------------------------------------------------------


def test_basic_arduino_io(serial_handlers):
    queue = queue_module.Queue(maxsize=1)
    assert queue.empty()
    aio = arduino_io.ArduinoIO(
        'telemetry',
        'arduinosimulator://?board=telemetry',
        queue,
        serial_config=dict(open_delay=0))
    aio.stop_reading()
    aio.disconnect()
    aio.write('foo=1\n')
    aio.disconnect()
    aio.stop_reading()
    try:
        first_reading = None
        try:
            assert queue.empty()
            aio.start_reading()
            while queue.empty():
                time.sleep(0.05)
            first_reading = aio.last_reading()
            assert queue.qsize() == 1
            # Wait for one more reading, which will fail to be added due
            # to the full queue; we can check for this by looking in the
            # log file manually. Not sure that it is worth doing in code.
            time.sleep(2.1)
            assert queue.qsize() == 1
        finally:
            aio.stop_reading()
        item = queue.get_nowait()
        assert item is not None
        assert item == first_reading
        assert aio.last_reading() != item
    finally:
        aio.stop_reading()
        aio.disconnect()
