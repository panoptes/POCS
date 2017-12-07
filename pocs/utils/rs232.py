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
                 name="serial_data",
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

        self.name = name
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
        connected = False
        if self.ser:
            connected = self.ser.isOpen()

        return connected

    def connect(self):
        """Actually set up the Thread and connect to serial."""
        # TODO(jamessynge): Determine if we need this since the serial port is opened
        # when the instance is created.
        self.logger.debug('Serial connect called')
        if not self.ser.isOpen():
            try:
                self.ser.open()
            except serial.serialutil.SerialException as err:
                raise BadSerialConnection(msg=err)

        if not self.ser.isOpen():
            raise BadSerialConnection(msg="Serial connection is not open")

        self.logger.debug('Serial connection established to {}'.format(
            self.name))
        return self.ser.isOpen()

    def disconnect(self):
        """Closes the serial connection.

        Returns:
            bool: Indicates if closed or not
        """
        self.ser.close()
        return not self.is_connected

    def write(self, value):
        """Write value (a string) after encoding as bytes."""
        assert self.ser
        assert self.ser.isOpen()

        # self.logger.debug('Serial write: {}'.format(value))
        response = self.ser.write(value.encode())

        return response

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

        # self.logger.debug('Serial read: {}'.format(response_string))
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
