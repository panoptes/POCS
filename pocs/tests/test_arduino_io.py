# Test sensors.py ability to read from two sensor boards.

import collections
import contextlib
import datetime
import pytest
import serial
import threading
import time

from pocs.sensors import arduino_io
import pocs.utils.error as error
from pocs.utils.logger import get_root_logger
from pocs.utils import CountdownTimer
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


def read_and_return(aio, db, retry_limit=10):
    """Ask the ArduinioIO instance to read_and_record, then return the reading.

    The first line of output might be a partial report: leading bytes might be
    missing, Therefore we allow for retrying.
    """
    old_reading = db.get_current(aio.board)

    for _ in range(retry_limit):
        if aio.read_and_record():
            new_reading = db.get_current(aio.board)
            assert old_reading is not new_reading
            return new_reading

    # Should only be able to get here if the retry limit was too low.
    assert retry_limit < 1


def receive_message_with_timeout(subscriber, timeout_secs=1.0):
    """Receive the next message from a subscriber channel."""
    timer = CountdownTimer(timeout_secs)
    while True:
        topic, msg_obj = subscriber.receive_message(blocking=False)
        if topic or msg_obj:
            return topic, msg_obj
        if not timer.sleep(max_sleep=0.05):
            return None, None


@contextlib.contextmanager
def open_serial_device(*args, **kwargs):
    """Context manager that opens a serial device, disconnects at exit.

    Ensures that an serial device is disconnected when exiting, which
    in turn ensures that the Arduino simulator is shutdown.
    """
    ser = arduino_io.open_serial_device(*args, **kwargs)
    try:
        yield ser
    finally:
        ser.disconnect()


# --------------------------------------------------------------------------------------------------
# Basic tests of FakeArduinoSerialHandler.


def test_create_camera_simulator(serial_handlers):
    """Test SerialData, FakeArduinoSerialHandler and ArduinoSimulator."""
    port = 'arduinosimulator://?board=camera'
    ser = rs232.SerialData(port=port, baudrate=9600, timeout=2.0)
    try:
        assert ser.is_connected is True

        # Some testing/coverage of the underlying handler and simulator...

        ser.ser.open()  # Redundant, but covers a branch.

        # There is nothing in the output buffer, so resetting it should
        # have no effect.
        assert ser.ser.out_waiting == 0
        ser.ser.reset_output_buffer()
        assert ser.ser.out_waiting == 0

        # If we flush the input, we'll be able to find zero bytes waiting eventually.
        was_empty = False
        for n in range(10):
            ser.reset_input_buffer()
            if ser.ser.in_waiting == 0:
                was_empty = True
                break
        assert was_empty

        ser.disconnect()
        assert ser.is_connected is False

        # Various methods throw if the device isn't connected/open.
        with pytest.raises(Exception):
            ser.ser.in_waiting
        with pytest.raises(Exception):
            ser.ser.out_waiting
        with pytest.raises(Exception):
            ser.ser.read()
        with pytest.raises(Exception):
            ser.ser.flush()
        with pytest.raises(Exception):
            ser.ser.reset_output_buffer()

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

        # If we write a bunch of commands, eventually we can detect that the
        # underlying serial device has pending output.
        was_full = 0
        for n in range(20):
            ser.write('some bytes, again and again')
            if ser.ser.out_waiting > 0:
                was_full += 1
                if was_full > 3:
                    ser.ser.reset_output_buffer()
                    break
                ser.ser.flush()
        assert was_full > 0

        # Read until times out, at which point read will return
        # whatever it has accumulated.
        ser.ser.timeout = 0.1
        total = 0
        for n in range(20):
            total += len(ser.read_bytes(size=None))
        assert total > 0

        ser.disconnect()
        assert ser.is_connected is False
    finally:
        ser.disconnect()


def test_create_default_simulator(serial_handlers):
    """Defaults to creating telemetry_board messages."""
    ser = arduino_io.open_serial_device('arduinosimulator://')
    assert ser.is_connected is True
    retry_limit = 2
    (ts, reading) = ser.get_and_parse_reading(retry_limit=retry_limit)
    assert isinstance(reading, dict)
    assert reading['name'] == 'telemetry_board'
    report_num = reading['report_num']
    assert 1 <= report_num
    assert report_num <= retry_limit
    ser.disconnect()
    assert ser.is_connected is False


def test_create_simulator_small_read_buffer(serial_handlers):
    """Force the communication to be difficult by making a very small buffer.

    This should force more code paths to be covered.
    """
    ser = arduino_io.open_serial_device(
        'arduinosimulator://?board=telemetry&read_buffer_size=1&chunk_size=1')
    assert ser.is_connected is True
    # Wait a bit so that the read buffer overflows.
    time.sleep(4)
    # Now start reading, which will certainly require some retries
    # on very busy machines.
    retry_limit = 2000
    (ts, reading) = ser.get_and_parse_reading(retry_limit=retry_limit)
    assert isinstance(reading, dict)
    assert reading['name'] == 'telemetry_board'
    report_num = reading['report_num']
    assert 1 < report_num
    assert report_num <= retry_limit
    ser.disconnect()
    assert ser.is_connected is False


# --------------------------------------------------------------------------------------------------


def test_detect_board_on_port_invalid_port():
    """detect_board_on_port will fail if the port is bogus."""
    assert arduino_io.detect_board_on_port(' not a valid port ', logger=get_root_logger()) is None


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


def test_arduino_io_basic(serial_handlers, memory_db, msg_publisher, msg_subscriber, cmd_publisher,
                          cmd_subscriber):
    board = 'telemetry'
    port = 'arduinosimulator://?board=' + board
    board = board + '_board'
    with open_serial_device(port) as ser:
        aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

        # Wait until we get the first reading.
        stored_reading = read_and_return(aio, memory_db)
        assert isinstance(stored_reading, dict)
        assert sorted(stored_reading.keys()) == ['_id', 'data', 'date', 'type']
        assert isinstance(stored_reading['_id'], str)
        assert isinstance(stored_reading['date'], datetime.datetime)
        assert stored_reading['type'] == board

        # Check that the reading was sent as a message. We need to allow some
        # time for the message to pass through thee messaging system.
        topic, msg_obj = receive_message_with_timeout(msg_subscriber)
        assert topic == board
        assert isinstance(msg_obj, dict)
        assert len(msg_obj) == 3
        assert isinstance(msg_obj.get('data'), dict)
        assert isinstance(msg_obj.get('timestamp'), str)
        assert msg_obj.get('name') == board
        assert stored_reading['data']['data'] == msg_obj['data']

        # Check that the reading was stored.
        stored_reading = memory_db.get_current(board)
        assert isinstance(stored_reading, dict)
        assert sorted(stored_reading.keys()) == ['_id', 'data', 'date', 'type']
        assert isinstance(stored_reading['_id'], str)
        assert stored_reading['data']['data'] == msg_obj['data']
        assert isinstance(stored_reading['date'], datetime.datetime)
        assert stored_reading['type'] == board

        # There should be no new messages because we haven't called read_and_record again.
        topic, msg_obj = receive_message_with_timeout(msg_subscriber, timeout_secs=0.2)
        assert topic is None
        assert msg_obj is None


def test_arduino_io_auto_connect_to_read(serial_handlers, memory_db, msg_publisher, msg_subscriber,
                                         cmd_publisher, cmd_subscriber):
    """Exercise ability to reconnect if disconnected."""
    board = 'camera'
    port = 'arduinosimulator://?board=' + board
    board = board + '_board'
    with open_serial_device(port) as ser:
        aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

        read_and_return(aio, memory_db)
        aio.reconnect()
        read_and_return(aio, memory_db)
        aio.disconnect()
        read_and_return(aio, memory_db)


def test_arduino_io_board_name(serial_handlers, memory_db, msg_publisher, msg_subscriber,
                               cmd_publisher, cmd_subscriber):
    board = 'telemetry'
    port = 'arduinosimulator://?board=' + board
    board = board + '_board'
    with open_serial_device(port) as ser:
        aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

        # Confirm that it checks the name of the board. If the reading contains
        # a 'name', it must match the expected value.
        aio.board = 'wrong'
        with pytest.raises(error.ArduinoDataError):
            read_and_return(aio, memory_db)
        aio.board = board


def test_arduino_io_shutdown(serial_handlers, memory_db, msg_publisher, msg_subscriber,
                             cmd_publisher, cmd_subscriber):
    """Confirm request to shutdown is recorded."""
    board = 'telemetry'
    port = 'arduinosimulator://?board=' + board
    board = board + '_board'
    with open_serial_device(port) as ser:
            aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

            # Ask it to stop working. Just records the request in a private variable,
            # but if we'd been running it in a separate process this is how we'd get it
            # to shutdown cleanly; the alternative would be to kill the process.
            cmd_topic = board + ':commands'
            assert cmd_topic == aio._cmd_topic

            # Direct manipulation of stop_running should work.
            assert not aio.stop_running
            aio.stop_running = True
            assert aio.stop_running
            aio.stop_running = False
            assert not aio.stop_running

            # And we should be able to send it the command over the command messaging system.
            get_root_logger().debug('Sending shutdown command')
            cmd_publisher.send_message(cmd_topic, dict(command='shutdown'))
            # stop_running should still be False since we've not yet called handle_commands.
            assert not aio.stop_running

            # On a lightly loaded system, the send_message will work quickly, so that
            # the first call to handle_commands receives it, but it might take longer
            # sometimes.
            for _ in range(10):
                aio.handle_commands()
                if aio.stop_running:
                    break
                get_root_logger().debug('Shutdown not handled yet')
                get_root_logger().debug('ArduinoIO.stop_running == {!r}', aio.stop_running)

            assert aio.stop_running


def test_arduino_io_write_line(serial_handlers, memory_db, msg_publisher, msg_subscriber,
                               cmd_publisher, cmd_subscriber):
    """Confirm request to shutdown is recorded."""
    board = 'telemetry'
    port = 'arduinosimulator://?board=' + board
    board = board + '_board'
    with open_serial_device(port) as ser:
        aio = arduino_io.ArduinoIO(board, ser, memory_db, msg_publisher, cmd_subscriber)

        cmd_topic = board + ':commands'
        assert cmd_topic == aio._cmd_topic

        # Run ArduinoIO in a thread.
        thread = threading.Thread(target=lambda: aio.run(), daemon=True)
        thread.start()

        # Wait until messages are received, with a time limit.
        topic, msg_obj = msg_subscriber.receive_message(blocking=True, timeout_ms=20000)
        assert topic
        assert msg_obj
        assert 'commands' not in msg_obj['data']

        # Drain available messages.
        for n in range(100):
            topic, msg_obj = msg_subscriber.receive_message(blocking=False)
            if not topic:
                print(f'Drained at n=#{n}')
                break

        # Send a command. The simulator will echo it.
        cmd_publisher.send_message(cmd_topic, dict(command='write_line', line='relay=on'))

        # Look for a message with our command echoed.
        for n in range(5):
            topic, msg_obj = msg_subscriber.receive_message(blocking=True, timeout_ms=3000)
            if 'commands' in msg_obj['data']:
                break

        assert 'commands' in msg_obj['data']
        assert msg_obj['data']['commands'] == ['relay=on']

        # Confirm that later messages don't have any commands.
        topic, msg_obj = msg_subscriber.receive_message(blocking=True, timeout_ms=3000)
        assert 'commands' not in msg_obj['data']

        # Send another command. The simulator will echo it.
        cmd_publisher.send_message(cmd_topic, dict(command='write_line', line='relay=off'))

        # Look for a message with our command echoed.
        for n in range(5):
            topic, msg_obj = msg_subscriber.receive_message(blocking=True, timeout_ms=3000)
            if 'commands' in msg_obj['data']:
                break

        assert 'commands' in msg_obj['data']
        assert msg_obj['data']['commands'] == ['relay=off']

        # Confirm that later messages don't have any commands.
        topic, msg_obj = msg_subscriber.receive_message(blocking=True, timeout_ms=3000)
        assert 'commands' not in msg_obj['data']

        # Shutdown in the expected style.
        assert not aio.stop_running
        cmd_publisher.send_message(cmd_topic, dict(command='shutdown'))
        thread.join(timeout=10.0)
        assert not thread.is_alive()
        assert aio.stop_running
