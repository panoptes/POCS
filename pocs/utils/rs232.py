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

    def __init__(self, port=None, baudrate=115200, threaded=True, name="serial_data"):
        PanBase.__init__(self)

        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baudrate
            self.is_threaded = threaded

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
            self.queue = deque([], 1)
            self._is_listening = False
            self.loop_delay = 2.

            if self.is_threaded:
                self._serial_io = TextIOWrapper(BufferedRWPair(self.ser, self.ser),
                                                newline='\r\n', encoding='ascii', line_buffering=True)

                self.logger.debug("Using threads (multiprocessing)")
                self.process = Thread(target=self.receiving_function, args=(self.queue,))
                self.process.daemon = True
                self.process.name = "PANOPTES_{}".format(name)

            self.logger.debug('Serial connection set up to {}, sleeping for two seconds'.format(self.name))
            time.sleep(2)
            self.logger.debug('SerialData created')
        except Exception as err:
            self.ser = None
            self.logger.critical('Could not set up serial port {} {}'.format(port, err))

    @property
    def is_connected(self):
        """
        Checks the serial connection on the mount to determine if connection is open
        """
        connected = False
        if self.ser:
            connected = self.ser.isOpen()

        return connected

    @property
    def is_listening(self):
        return self._is_listening

    def start(self):
        """ Starts the separate process """
        self.logger.debug("Starting serial process: {}".format(self.process.name))
        self._is_listening = True
        self.process.start()

    def stop(self):
        """ Starts the separate process """
        self.logger.debug("Stopping serial process: {}".format(self.process.name))
        self._is_listening = False
        self.process.join()

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

        self.logger.debug('Serial connection established to {}'.format(self.name))
        return self.ser.isOpen()

    def disconnect(self):
        """Closes the serial connection

        Returns:
            bool: Indicates if closed or not
        """
        self.ser.close()
        return not self.is_connected

    def receiving_function(self, q):
        self.connect()
        while self.is_listening:
            try:
                line = self.read()
                ts = time.strftime('%Y-%m-%dT%H:%M:%S %Z', time.gmtime())
                self.queue.append((ts, line))
            except IOError as err:
                self.logger.warning("Device is not sending messages. IOError: {}".format(err))
                time.sleep(2)
            except UnicodeDecodeError:
                self.logger.warning("Unicode problem")
                time.sleep(2)
            except Exception:
                self.logger.warning("Unknown problem")

            time.sleep(self.loop_delay)

    def write(self, value):
        """
            For now just pass the value along to serial object
        """
        assert self.ser
        assert self.ser.isOpen()

        # self.logger.debug('Serial write: {}'.format(value))
        if self.is_threaded:
            response = self._serial_io.write(value)
        else:
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
            if self.is_threaded:
                response_string = self._serial_io.readline()
            else:
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
            if self.is_threaded:
                info = self.queue.pop()
            else:
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
