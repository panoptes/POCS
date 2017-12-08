import serial as serial
import time

from io import BufferedRWPair
from io import TextIOWrapper

from collections import deque
from threading import Thread

from .. import PanBase
from .error import BadSerialConnection


class SerialData(PanBase):
    """
    Main serial class
    """

    def __init__(self,
                 port=None,
                 baudrate=115200,
                 threaded=None,
                 name=None,
                 open_delay=2.0,
                 retry_limit=5,
                 retry_delay=0.5):
        """Init a SerialData instance.

        Args:
            port: The port (e.g. /dev/tty123 or socket://host:port) to which to
                open a connection.
            baudrate: For true serial lines (e.g. RS-232), sets the baud rate of
                the device.
            threaded: Obsolete, ignored.
            name: Name of this object.
            open_delay: Seconds to wait after opening the port.
            retry_limit: Number of times to try readline() calls in read().
            retry_delay: Delay between readline() calls in read().
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

        # Properties have been set to reasonable values, ready to open the port.
        self.ser.open()

        open_delay = max(0.0, float(open_delay))
        self.logger.debug(
            'Serial connection set up to %r, sleeping for %r seconds', self.name, open_delay)
        if open_delay > 0.0:
            time.sleep(open_delay)
        self.logger.debug('SerialData created')

    @property
    def is_connected(self):
        """True if serial port is open, False otherwise."""
        if self.ser:
            return self.ser.is_open
        return False

    def connect(self):
        """If disconnected, then connect to the serial port."""
        # TODO(jamessynge): Determine if we need this since the serial port is opened
        # when the instance is created. I.e. do we ever disconnect and re-connect?
        self.logger.debug('Serial connect called')
        if self.is_connected:
            return True
        try:
            self.ser.open()
            if not self.is_connected:
                raise BadSerialConnection(msg="Serial connection {} is not open".format(self.name))
        except serial.serialutil.SerialException as err:
            raise BadSerialConnection(msg=err)
        self.logger.debug('Serial connection established to {}'.format(self.name))
        return True

    def disconnect(self):
        """Closes the serial connection.

        Returns:
            bool: True if not connected
        """
        self.ser.close()
        return not self.is_connected

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
        """Read a line and return the timestamp of the read.

        Returns:
            str: Item in queue
        """

        # TODO(jamessynge): Consider collecting the time (utc?) after the read completes,
        # so that long delays reading don't appear to have happened much earlier.
        try:
            ts = time.strftime('%Y-%m-%dT%H:%M:%S %Z', time.gmtime())
            info = (ts, self.read())
        except IndexError:
            raise IndexError
        else:
            return info

    def clear_buffer(self):
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
            # been set, in which case reading that field will generate a NameError.
            ser = self.ser
        except NameError:
            return
        if ser:
            self.ser.close()
