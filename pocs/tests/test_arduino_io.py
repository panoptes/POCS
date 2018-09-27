# Test sensors.py ability to read from two sensor boards.

import collections
import datetime
import pytest
import serial

from pocs.sensors import arduino_io
import pocs.utils.error as error
from pocs.utils.logger import get_root_logger
from pocs.utils import rs232

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
    ser = arduino_io.open_serial_device('arduinosimulator://')
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
    assert arduino_io.detect_board_on_port('loop://', logger=get_root_logger()) is None


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


def test_detect_board_on_port_no_name(serial_handlers):
    """Deal with dict that doesn't contain a name."""
    assert arduino_io.detect_board_on_port('arduinosimulator://?board=json_object') is None


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


def test_auto_detect_arduino_devices(inject_get_serial_port_info, serial_handlers, fake_logger):
    v = arduino_io.auto_detect_arduino_devices()
    assert len(v) == 2
    for ndx, (board, name) in enumerate([('telemetry', 't1'), ('camera', 'c1')]):
        print('ndx=%r   board=%r   name=%r' % (ndx, board, name))
        expected = 'arduinosimulator://?board=%s&name=%s' % (board, name)
        assert v[ndx][0] == '{}_board'.format(board)
        assert v[ndx][1] == expected

    # Confirm that params are handled properly
    u = arduino_io.auto_detect_arduino_devices(ports=[v[0][1]], logger=fake_logger)
    assert len(u) == 1
    assert u[0] == v[0]


# --------------------------------------------------------------------------------------------------


def test_basic_arduino_io(serial_handlers, memory_db, msg_publisher, msg_subscriber, cmd_publisher,
                          cmd_subscriber):
    board = 'telemetry'
    ser = arduino_io.open_serial_device('arduinosimulator://?board=' + board)
    board = board + '_board'
    aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

    # Exercise ability to reconnect if disconnected.
    aio.reconnect()
    aio.disconnect()

    got_reading = aio.read_and_record()
    if got_reading is False:
        got_reading = aio.read_and_record()
        assert got_reading is True
    else:
        assert got_reading is True

    # Check that the reading was sent as a message.
    topic, msg_obj = msg_subscriber.receive_message(blocking=False)
    assert topic == board
    assert isinstance(msg_obj, dict)
    assert len(msg_obj) == 3
    assert isinstance(msg_obj.get('data'), dict)
    assert isinstance(msg_obj.get('timestamp'), str)
    assert msg_obj.get('name') == board

    # Check that the reading was stored.
    stored_reading = memory_db.get_current(board)
    assert isinstance(stored_reading, dict)
    assert sorted(stored_reading.keys()) == ['_id', 'data', 'date', 'type']
    assert isinstance(stored_reading['_id'], str)
    assert stored_reading['data']['data'] == msg_obj['data']
    assert isinstance(stored_reading['date'], datetime.datetime)
    assert stored_reading['type'] == board

    # There should be no new messages because we haven't called read_and_record again.
    topic, msg_obj = msg_subscriber.receive_message(blocking=False)
    assert topic is None
    assert msg_obj is None

    # Send a command. For now, just a string to be sent.
    # TODO(jamessynge): Add named based setting of relays.
    # TODO(jamessynge): Add some validation of the effect of the command.
    cmd_topic = board + ':commands'
    assert cmd_topic == aio._cmd_topic
    cmd_publisher.send_message(cmd_topic, dict(command='write_line', line='relay=on'))
    aio.handle_commands()

    # Confirm that it checks the name of the board. If the reading contains
    # a 'name', it must match the expected value.
    aio.board = 'wrong'
    with pytest.raises(error.ArduinoDataError):
        aio.read_and_record()
    aio.board = board

    # Ask it to stop working. Just records the request in a private variable,
    # but if we'd been running it in a separate process this is how we'd get it
    # to shutdown cleanly; the alternative would be to kill the process.
    cmd_publisher.send_message(cmd_topic, dict(command='shutdown'))
    assert aio._keep_running
    aio.handle_commands()
    assert not aio._keep_running
