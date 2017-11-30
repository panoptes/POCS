import pytest
import serial

from pocs.utils import rs232
from pocs.utils.config import load_config

from pocs.tests.serial_handlers import NoOpSerial
from pocs.tests.serial_handlers import protocol_buffers
from pocs.tests.serial_handlers import protocol_no_op
from pocs.tests.serial_handlers import protocol_hooked


def test_detect_uninstalled_scheme():
    """If our handlers aren't installed, will detect unknown scheme."""
    with pytest.raises(ValueError):
        rs232.SerialData(port='no_op://')


@pytest.fixture(scope='module')
def handler():
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.append('pocs.tests.serial_handlers')
    yield True
    # Remove our test handlers.
    serial.protocol_handler_packages.remove('pocs.tests.serial_handlers')


def test_detect_bogus_scheme(handler):
    """When our handlers are installed, will still detect unknown scheme."""
    with pytest.raises(ValueError):
        rs232.SerialData(port='bogus://')


@pytest.fixture(scope="function", params=[False, True])
def threaded(request):
    yield request.param


def test_basic_no_op(handler, threaded):
    # Confirm we can create the SerialData object.
    ser = rs232.SerialData(port='no_op://', open_delay=0, threaded=threaded)

    # Peek inside, it should have a NoOpSerial instance as member ser.
    assert ser.ser
    assert isinstance(ser.ser, NoOpSerial)

    # Open is automatically called by SerialData.
    assert ser.is_connected

    # Listener not started, whether threaded or not.
    assert ser.is_threaded == threaded
    assert not ser.is_listening

    # If threaded, start the listener.
    if threaded:
        ser.start()
        assert ser.is_listening
        assert ser.is_threaded

    # no_op handler doesn't do any reading, analogous to /dev/null, which
    # never produces any output.
    assert '' == ser.read(retry_delay=0.01, retry_limit=2)

    # Assert how much is written, which unfortunately isn't consistent.
    if threaded:
        assert 6 == ser.write('abcdef')
    else:
        assert 0 == ser.write('abcdef')

    # If threaded, stop the listener.
    if threaded:
        assert ser.is_threaded
        assert ser.is_listening
        ser.stop()
        assert not ser.is_listening

    # Disconnect from the serial port.
    assert ser.is_connected
    ser.disconnect()
    assert not ser.is_connected
    assert not ser.is_listening

    # Should no longer be able to read or write.
    with pytest.raises(AssertionError):
        ser.read(retry_delay=0.01, retry_limit=1)
    with pytest.raises(AssertionError):
        ser.write('a')


def test_basic_io(handler, threaded):
    protocol_buffers.ResetBuffers(b'abc\r\n')
    ser = rs232.SerialData(port='buffers://', open_delay=0, threaded=threaded)

    # Peek inside, it should have a BuffersSerial instance as member ser.
    assert isinstance(ser.ser, protocol_buffers.BuffersSerial)

    # Listener not started, whether threaded or not.
    assert ser.is_threaded == threaded
    assert not ser.is_listening

    # If threaded, start the listener.
    if threaded:
        ser.start()
        assert ser.is_listening
        assert ser.is_threaded
        pytest.set_trace()

    # Can read one line, "abc\r\n", from the read buffer.
    assert 'abc\r\n' == ser.read(retry_delay=0.1, retry_limit=10)
    # Another read will fail, having exhausted the contents of the read buffer.
    assert '' == ser.read(retry_delay=0.01, retry_limit=2)

    # Can write to the "device", the handler will accumulate the results.
    assert 5 == ser.write('def\r\n')
    assert 6 == ser.write('done\r\n')

    assert b'def\r\ndone\r\n' == protocol_buffers.GetWBufferValue()

    # If we add more to the read buffer, we can read again.
    protocol_buffers.SetRBufferValue(b'line1\r\nline2\r\ndangle')
    assert 'line1\r\n' == ser.read(retry_delay=10, retry_limit=20)
    assert 'line2\r\n' == ser.read(retry_delay=10, retry_limit=20)
    assert 'dangle' == ser.read(retry_delay=10, retry_limit=20)

    ser.disconnect()
    assert not ser.is_connected


class ThreadedHandler(protocol_no_op.Serial):
    pass


def test_threaded_io(handler):
    protocol_hooked.Serial = ThreadedHandler
    protocol_buffers.ResetBuffers(b'abc\r\n')
    #pytest.set_trace()
    ser = rs232.SerialData(port='hooked://', open_delay=0, threaded=False)
    assert ser
    # Peek inside, it should have a PySerial instance as member ser.
    assert ser.ser
    assert ser.ser.__class__.__name__ == 'ThreadedHandler'
    print(str(ser.ser))
    # Open is automatically called by SerialData.
    assert ser.is_connected
    # Not threaded, and so listener not started.
    assert not ser.is_threaded
    assert not ser.is_listening
    
    return

    # Can read one line, "abc\r\n", from the read buffer.
    assert 'abc\r\n' == ser.read(retry_delay=10, retry_limit=20)
    # Another read will fail, having exhausted the contents of the read buffer.
    assert '' == ser.read(retry_delay=0.01, retry_limit=2)

    # Can write to the "device", the handler will accumulate the results.
    assert 5 == ser.write('def\r\n')
    assert 6 == ser.write('done\r\n')

    assert b'def\r\ndone\r\n' == protocol_buffers.GetWBufferValue()

    # If we add more to the read buffer, we can read again.
    protocol_buffers.SetRBufferValue(b'line1\r\nline2\r\ndangle')
    assert 'line1\r\n' == ser.read(retry_delay=10, retry_limit=20)
    assert 'line2\r\n' == ser.read(retry_delay=10, retry_limit=20)
    pytest.set_trace()
    assert 'dangle' == ser.read(retry_delay=10, retry_limit=20)
    

    ser.disconnect()
    assert not ser.is_connected
    assert not ser.is_listening

