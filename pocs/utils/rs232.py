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
                 name="serial_data"):
        """Init a SerialData instance.

        Args:
            port: The port (e.g. /dev/tty123 or socket://host:port) to which to
                open a connection.
            baudrate: For true serial lines (e.g. RS-232), sets the baud rate of
                the device.
            threaded: Obsolete, ignored.
            name: Name of this object.
        """
        PanBase.__init__(self)

        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baudrate

            self.ser.bytesize = serial.EIGHTBITS
            self.ser.parity = serial.PARITY_NONE
            self.ser.stopbits = serial.STOPBITS_ONE
            self.ser.timeout = 1.0
            self.ser.xonxoff = False
            self.ser.rtscts = False
            self.ser.dsrdtr = False
            self.ser.write_timeout = False
            self.ser.open()

            self.name = name

            self.logger.debug(
                'Serial connection set up to {}, sleeping for two seconds'.format(
                    self.name))
            time.sleep(2)
            self.logger.debug('SerialData created')
        except Exception as err:
            self.ser = None
            self.logger.critical('Could not set up serial port {} {}'.format(
                port, err))

    @property
    def is_connected(self):
        """
        Checks the serial connection on the mount to determine if connection is open
        """
        connected = False
        if self.ser:
            connected = self.ser.isOpen()

        return connected

    def connect(self):
        """ Actually set up the Thread and connect to serial """

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
        """Closes the serial connection

        Returns:
            bool: Indicates if closed or not
        """
        self.ser.close()
        return not self.is_connected

    def write(self, value):
        """
            For now just pass the value along to serial object
        """
        assert self.ser
        assert self.ser.isOpen()

        # self.logger.debug('Serial write: {}'.format(value))
        response = self.ser.write(value.encode())

        return response

    def read(self):
        """
        Reads value using readline
        If no response is given, delay and then try to read again. Fail after 10 attempts
        """
        assert self.ser
        assert self.ser.isOpen()

        retry_limit = 5
        delay = 0.5

        while True and retry_limit:
            response_string = self.ser.readline(self.ser.inWaiting()).decode()
            if response_string > '':
                break
            time.sleep(delay)
            retry_limit -= 1

        # self.logger.debug('Serial read: {}'.format(response_string))

        return response_string

    def get_reading(self):
        """ Get reading from the queue

        Returns:
            str: Item in queue
        """

        try:
            ts = time.strftime('%Y-%m-%dT%H:%M:%S %Z', time.gmtime())
            info = (ts, self.read())
        except IndexError:
            raise IndexError
        else:
            return info

    def clear_buffer(self):
        """ Clear Response Buffer """
        count = 0
        while self.ser.inWaiting() > 0:
            count += 1
            self.ser.read(1)

        # self.logger.debug('Cleared {} bytes from buffer'.format(count))

    def __del__(self):
        if self.ser:
            self.ser.close()
