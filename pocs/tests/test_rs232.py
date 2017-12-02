import io
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


def test_basic_no_op(handler):
    # Confirm we can create the SerialData object.
    ser = rs232.SerialData(port='no_op://', open_delay=0, threaded=False)

    # Peek inside, it should have a NoOpSerial instance as member ser.
    assert ser.ser
    assert isinstance(ser.ser, NoOpSerial)

    # Open is automatically called by SerialData.
    assert ser.is_connected

    # no_op handler doesn't do any reading, analogous to /dev/null, which
    # never produces any output.
    assert '' == ser.read(retry_delay=0.01, retry_limit=2)
    assert 0 == ser.write('abcdef')

    # Disconnect from the serial port.
    assert ser.is_connected
    ser.disconnect()
    assert not ser.is_connected

    # Should no longer be able to read or write.
    with pytest.raises(AssertionError):
        ser.read(retry_delay=0.01, retry_limit=1)
    with pytest.raises(AssertionError):
        ser.write('a')


def test_basic_io(handler):
    protocol_buffers.ResetBuffers(b'abc\r\n')
    ser = rs232.SerialData(port='buffers://', open_delay=0, threaded=False)

    # Peek inside, it should have a BuffersSerial instance as member ser.
    assert isinstance(ser.ser, protocol_buffers.BuffersSerial)

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


class HookedSerialHandler(NoOpSerial):
    """Sources a line of text repeatedly, and sinks an infinite amount of input."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.r_buffer = io.BytesIO(
            b"{'a': 12, 'b': [1, 2, 3, 4], 'c': {'d': 'message'}}\r\n")

    @property
    def in_waiting(self):
        """The number of input bytes available to read immediately."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        total = len(self.r_buffer.getbuffer())
        avail = total - self.r_buffer.tell()
        # If at end of the stream, reset the stream.
        if avail <= 0:
            self.r_buffer.seek(0)
            avail = total
        return avail

    def open(self):
        """Open port.

        Raises:
            SerialException if the port cannot be opened.
        """
        self.is_open = True

    def close(self):
        """Close port immediately."""
        self.is_open = False

    def read(self, size=1):
        """Read until the end of self.r_buffer, then seek to beginning of self.r_buffer."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        # If at end of the stream, reset the stream.
        avail = self.in_waiting
        return self.r_buffer.read(min(size, self.in_waiting))

    def write(self, data):
        """Write data to bitbucket."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        return len(data)


def test_hooked_io(handler):
    protocol_hooked.Serial = HookedSerialHandler
    ser = rs232.SerialData(port='hooked://', open_delay=0, threaded=False)

    # Peek inside, it should have a PySerial instance as member ser.
    assert ser.ser
    assert ser.ser.__class__.__name__ == 'HookedSerialHandler'
    print(str(ser.ser))

    # Open is automatically called by SerialData.
    assert ser.is_connected

    # Can read many identical lines from ser.
    first_line = None
    for n in range(20):
        line = ser.read(retry_delay=10, retry_limit=20)
        if first_line:
            assert line == first_line
        else:
            first_line = line
            assert 'message' in line

    # Can write to the "device" many times.
    line = 'abcdefghijklmnop' * 30
    line = line + '\r\n'
    for n in range(20):
        assert len(line) == ser.write(line)

    ser.disconnect()
    assert not ser.is_connected
