import multiprocessing
import serial as serial
import time

from .. import PanBase
from .error import BadSerialConnection


class SerialData(PanBase):

    """
    Main serial class
    """

    def __init__(self, port=None, baudrate=9600, threaded=True, name="serial_data"):
        PanBase.__init__(self)

        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baudrate
            self.is_threaded = threaded

            self.ser.bytesize = serial.EIGHTBITS
            self.ser.parity = serial.PARITY_NONE
            self.ser.stopbits = serial.STOPBITS_ONE
            self.ser.timeout = 0.1
            self.ser.xonxoff = 0
            self.ser.rtscts = 0
            self.ser.interCharTimeout = None

            self.name = name
            self.serial_receiving = ''

            if self.is_threaded:
                self.logger.debug("Using threads (multiprocessing)")
                self.process = multiprocessing.Process(target=self.receiving_function)
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

    def start(self):
        """ Starts the separate process """
        self.logger.debug("Starting serial process: {}".format(self.process.name))
        self.process.start()

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

    def receiving_function(self):
        buffer = ''
        while True:
            try:
                buffer = buffer + self.read()
                if '\n' in buffer:
                    lines = buffer.split('\n')  # Guaranteed to have at least 2 entries
                    self.serial_receiving = lines[-2]
                    # If the Arduino sends lots of empty lines, you'll lose the
                    # last filled line, so you could make the above statement conditional
                    # like so: if lines[-2]: serial_receiving = lines[-2]
                    buffer = lines[-1]
            except IOError as err:
                print("Device is not sending messages. IOError: {}".format(err))
                time.sleep(2)
            except UnicodeDecodeError:
                print("Unicode problem")
                time.sleep(2)
            except:
                print("Uknown problem")

    def write(self, value):
        """
            For now just pass the value along to serial object
        """
        assert self.ser
        assert self.ser.isOpen()

        # self.logger.debug('Serial write: {}'.format(value))
        return self.ser.write(value.encode())

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
        if not self.ser:
            return 0
        for i in range(40):
            raw_line = self.serial_receiving
            try:
                return raw_line.strip()
            except ValueError:
                time.sleep(.005)
        return 0.

    def clear_buffer(self):
        """ Clear Response Buffer """
        count = 0
        while self.ser.inWaiting() > 0:
            count += 1
            contents = self.ser.read(1)

        # self.logger.debug('Cleared {} bytes from buffer'.format(count))

    def __del__(self):
        if self.ser:
            self.ser.close()
