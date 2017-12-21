"""Provides SerialData, a PySerial wrapper."""

import serial as serial
import time

from .. import PanBase
from .error import BadSerialConnection


class SerialData(PanBase):
    """SerialData wraps a PySerial instance for reading from and writing to a serial device.

    Because POCS is intended to be very long running, and hardware may be turned off when unused
    or to force a reset, this wrapper may or may not have an open connection to the underlying
    serial device. Note that for most devices, is_connected will return true if the device is
    turned off/unplugged after a connection is opened; the code will only discover there is a
    problem when we attempt to interact with the device.
    """

    def __init__(self,
                 port=None,
                 baudrate=115200,
                 name=None,
                 open_delay=0.0,
                 retry_limit=5,
                 retry_delay=0.5):
        """Create a SerialData instance and attempt to open a connection.

        The device need not exist at the time this is called, in which case is_connected will
        be false.

        Args:
            port: The port (e.g. /dev/tty123 or socket://host:port) to which to
                open a connection.
            baudrate: For true serial lines (e.g. RS-232), sets the baud rate of
                the device.
            name: Name of this object. Defaults to the name of the port.
            open_delay: Seconds to wait after opening the port.
            retry_limit: Number of times to try readline() calls in read().
            retry_delay: Delay between readline() calls in read().
        Raises:
            ValueError: If the serial parameters are invalid (e.g. a negative baudrate).

        """
        PanBase.__init__(self)

        if not port:
            raise ValueError('Must specify port for SerialData')

        self.name = name or port
        self.retry_limit = retry_limit
        self.retry_delay = retry_delay

        self.ser = serial.serial_for_url(port, do_not_open=True)

        # Configure the PySerial class.
        self.ser.baudrate = baudrate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 1.0
        self.ser.xonxoff = False
        self.ser.rtscts = False
        self.ser.dsrdtr = False
        self.ser.write_timeout = False

        self.logger.debug('SerialData for {} created', self.name)

        # Properties have been set to reasonable values, ready to open the port.
        try:
            self.ser.open()
        except serial.serialutil.SerialException as err:
            self.logger.debug('Unable to open {}. Error: {}', self.name, err)
            return

        open_delay = max(0.0, float(open_delay))
        if open_delay > 0.0:
            self.logger.debug('Opened {}, sleeping for {} seconds', self.name, open_delay)
            time.sleep(open_delay)
        else:
            self.logger.debug('Opened {}', self.name)

    @property
    def is_connected(self):
        """True if serial port is open, False otherwise."""
        return self.ser.is_open

    def connect(self):
        """If disconnected, then connect to the serial port.

        Raises:
            BadSerialConnection if unable to open the connection.
        """
        if self.is_connected:
            self.logger.debug('Connection already open to {}', self.name)
            return
        self.logger.debug('SerialData.connect called for {}', self.name)
        try:
            # Note: we must not call open when it is already open, else an exception is thrown of
            # the same type thrown when open fails to actually open the device.
            self.ser.open()
            if not self.is_connected:
                raise BadSerialConnection(msg="Serial connection {} is not open".format(self.name))
        except serial.serialutil.SerialException as err:
            raise BadSerialConnection(msg=err)
        self.logger.debug('Serial connection established to {}', self.name)
        return True

    def disconnect(self):
        """Closes the serial connection.

        Raises:
            BadSerialConnection if unable to close the connection.
        """
        # Fortunately, close() doesn't throw an exception if already closed.
        self.logger.debug('SerialData.disconnect called for {}', self.name)
        try:
            self.ser.close()
        except Exception as err:
            raise BadSerialConnection(
                msg="SerialData.disconnect failed for {}; underlying error: {}".format(
                    self.name, err))
        if self.is_connected:
            raise BadSerialConnection(msg="SerialData.disconnect failed for {}".format(self.name))

    def write_bytes(self, data):
        """Write data of type bytes."""
        assert self.ser
        assert self.ser.isOpen()
        return self.ser.write(data)

    def write(self, value):
        """Write value (a string) after encoding as bytes."""
        return self.write_bytes(value.encode())

    def read_bytes(self, size=1):
        """Reads size bytes from the serial port.

        If a read timeout is set on self.ser, this may return less characters than requested.
        With no timeout it will block until the requested number of bytes is read.

        Args:
            size: Number of bytes to read.
        Returns:
            Bytes read from the port.
        """
        assert self.ser
        assert self.ser.isOpen()
        return self.ser.read(size=size)

    def read(self, retry_limit=None, retry_delay=None):
        """Reads next line of input using readline.

        If no response is given, delay for retry_delay and then try to read
        again. Fail after retry_limit attempts.
        """
        assert self.ser
        assert self.ser.isOpen()

        if retry_limit is None:
            retry_limit = self.retry_limit
        if retry_delay is None:
            retry_delay = self.retry_delay

        while True and retry_limit:
            response_string = self.ser.readline(self.ser.inWaiting()).decode()
            if response_string > '':
                break
            time.sleep(retry_delay)
            retry_limit -= 1
        return response_string

    def get_reading(self):
        """Reads and returns a line, along with the timestamp of the read.

        Returns:
            A pair (tuple) of (timestamp, line). The timestamp is the time of completion of the
            readline operation.
        """
        # Get the timestamp after the read so that a long delay on reading doesn't make it
        # appear that the read happened much earlier than it did.
        line = self.read()
        ts = time.strftime('%Y-%m-%dT%H:%M:%S %Z', time.gmtime())
        info = (ts, line)
        return info

    def reset_input_buffer(self):
        """Clear buffered data from connected port/device.

        Note that Wilfred reports that the input from an Arduino can seriously lag behind
        realtime (e.g. 10 seconds), and that clear_buffer may exist for that reason (i.e. toss
        out any buffered input from a device, and then read the next full line, which likely
        requires tossing out a fragment of a line).
        """
        self.ser.reset_input_buffer()

    def __del__(self):
        """Close the serial device on delete.

        This is to avoid leaving a file or device open if there are multiple references
        to the serial.Serial object.
        """
        try:
            # If an exception is thrown when running __init__, then self.ser may not have
            # been set, in which case reading that field will generate a AttributeError.
            ser = self.ser
        except AttributeError:
            return
        if ser and ser.is_open:
            ser.close()
