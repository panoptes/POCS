# Supports reading from and writing to Arduinos attached via serial
# devices. Each line of output from the Arduinos must be a single
# JSON encoded object, one of whose fields is called "name" with the
# value the (unique) name of the board; e.g. "camera_board" or
# "telemetry_board".

import collections
import copy
import serial
import threading
import traceback

from panoptes.utils.error import ArduinoDataError
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import CountdownTimer
from panoptes.utils import rs232


def auto_detect_arduino_devices(ports=None):
    """Returns a list of tuples of (board_name, port)."""
    if ports is None:
        ports = get_arduino_ports()
    result = []
    for port in ports:
        board_name = detect_board_on_port(port)
        if board_name:
            result.append((board_name, port))
    return result


# Note: get_arduino_ports is modified by test_arduino_io.py, so if changing
# this import, the test will also need to be updated.
def get_arduino_ports():
    """Find ports (device paths or URLs) that appear to be Arduinos.

    Returns:
        a list of strings; device paths (e.g. /dev/ttyACM1) or URLs (e.g. rfc2217://host:port
        arduino_simulator://?board=camera).
    """
    ports = rs232.get_serial_port_info()
    return [
        p.device for p in ports
        if 'arduino' in p.description.lower() or 'arduino' in p.manufacturer.lower()
    ]


def detect_board_on_port(port):
    """Determine which type of board is attached to the specified port.

    Returns: Name of the board (e.g. 'camera_board') if we can read a
        line of JSON from the port, parse it and find a 'name'
        attribute in the top-level object. Else returns None.
    """
    logger = get_logger()
    logger.debug('Attempting to connect to serial port: {}'.format(port))
    serial_reader = None
    try:
        # First open a connection to the device.
        try:
            serial_reader = open_serial_device(port)
            if not serial_reader.is_connected:
                serial_reader.connect()
            logger.debug('Connected to {}', port)
        except Exception:
            logger.warning('Could not connect to port: {}'.format(port))
            return None
        try:
            reading = serial_reader.get_and_parse_reading(retry_limit=3)
            if not reading:
                return None
            (ts, data) = reading
            if isinstance(data, dict) and 'name' in data and isinstance(data['name'], str):
                return data['name']
            logger.warning('Unable to find board name in reading: {}', reading)
            return None
        except Exception as e:  # pragma: no cover
            logger.error('Exception while auto-detecting port {}: {}', port, e)
    finally:
        if serial_reader:
            serial_reader.disconnect()


def open_serial_device(port, serial_config=None, **kwargs):
    """Creates an rs232.SerialData for port, assumed to be an Arduino.

    Default parameters are provided when creating the SerialData
    instance, but may be overridden by serial_config or kwargs.

    Args:
        serial_config:
            dictionary (or None) with serial settings from config file,
            suitable for passing to SerialData or to a PySerial
            instance.
        **kwargs:
            Any other parameters to be passed to SerialData. These have
            higher priority than the serial_config parameter.
    """
    # Using a long timeout (2 times the report interval) rather than
    # retries which can just break a JSON line into two unparseable
    # fragments.
    defaults = dict(baudrate=9600, retry_limit=1, retry_delay=0, timeout=4.0, name=port)
    params = collections.ChainMap(dict(port=port), kwargs, serial_config or {}, defaults)
    params = dict(**params)
    return rs232.SerialData(**params)


class ArduinoIO(object):
    """Supports reading from and writing to Arduinos.

    The readings (python dictionaries) are recorded in a PanDB collection in
    the following form:

    ```
        {
          'name': self.board,
          'timestamp': t,
          'data': reading
        }
    ```

    """

    def __init__(self, board, serial_data, db):
        """Initialize for board on device.

        Args:
            board: The name of the board, used as the name of the database
                table/collection to write to, and the name of the messaging
                topics for readings or relay commands.
            serial_data: A SerialData instance connected to the board.
            db: The PanDB instance in which to record reading.
        """
        self.board = board.lower()
        self.port = serial_data.port
        self._serial_data = serial_data
        self._db = db
        self._logger = get_logger()
        self._last_reading = None
        self._report_next_reading = True
        self._cmd_topic = "{}:commands".format(board)
        # Using threading.Event rather than just a boolean field so that any thread
        # can get and set the stop_running property.
        self._stop_running = threading.Event()
        self._logger.info('Created ArduinoIO instance for board {}', self.board)

    @property
    def stop_running(self):
        return self._stop_running.is_set()

    @stop_running.setter
    def stop_running(self, value):
        if value:
            self._stop_running.set()
        else:
            self._stop_running.clear()
        self._logger.info('Updated ArduinoIO.stop_running to {!r}', self.stop_running)

    def run(self):
        """Main loop for recording data and reading commands.

        This only ends if an Exception is unhandled or if a 'shutdown'
        command is received. The most likely exception is from
        SerialData.get_and_parse_reading() in the event that the device
        disconnects from USB.
        """
        while not self.stop_running:
            self.read_and_record()
            self.handle_commands()

    def read_and_record(self):
        """Try to get the next reading and, if successful, record it.

        Write the reading to the appropriate PanDB collections and
        to the appropriate message topic.

        If there is an interruption in success in reading from the device,
        we announce (log) the start and end of that situation.
        """
        reading = self.get_reading()
        if not reading:
            # Consider adding an error counter.
            if not self._report_next_reading:
                self._logger.warning(
                    'Unable to read from {}. Will report when next successful read.',
                    self.port)
                self._report_next_reading = True
            return False
        if self._report_next_reading:
            self._logger.info('Succeeded in reading from {}; got:\n{}', self.port, reading)
            self._report_next_reading = False
        self.handle_reading(reading)
        return True

    def connect(self):
        """Connect to the port."""
        if not self._serial_data.is_connected:
            self._serial_data.connect()

    def disconnect(self):
        """Disconnect from the port.

        Will re-open automatically if reading or writing occurs.
        """
        try:
            if self._serial_data.is_connected:
                self._serial_data.disconnect()
        except Exception as e:
            self._logger.error('Failed to disconnect from {} due to: {}', self.port, e)

    def reconnect(self):
        """Disconnect from and connect to the serial port.

        This supports handling a SerialException, such as when the USB
        bus is reset.
        """
        try:
            self.disconnect()
        except Exception:
            self._logger.error('Unable to disconnect from {}', self.port)
            return False
        try:
            self.connect()
            return True
        except Exception:
            self._logger.error('Unable to reconnect to {}', self.port)
            return False

    def get_reading(self):
        """Reads and returns a single reading."""
        if not self._serial_data.is_connected:
            self._serial_data.connect()
        try:
            return self._serial_data.get_and_parse_reading(retry_limit=1)
        except serial.SerialException as e:
            self._logger.error('Exception raised while reading from port {}', self.port)
            self._logger.error('Exception: {}', "\n".join(traceback.format_exc()))
            if self.reconnect():
                return None
            raise e

    def handle_reading(self, reading):
        """Saves a reading as the last_reading and writes to output_queue."""
        # TODO(jamessynge): Discuss with Wilfred changing the timestamp to a datetime object
        # instead of a string. Obviously it needs to be serialized eventually.
        timestamp, data = reading
        if data.get('name', self.board) != self.board:
            msg = 'Board reports name {}, expected {}'.format(data['name'], self.board)
            self._logger.critical(msg)
            raise ArduinoDataError(msg)
        reading = dict(name=self.board, timestamp=timestamp, data=data)
        self._last_reading = copy.deepcopy(reading)
        if self._db:
            self._db.insert_current(self.board, reading)

    def handle_commands(self):
        """Read and process commands for up to 1 second.

        Returns when there are no more commands available from the
        command subscriber, or when a second has passed.
        The interval is 1 second because we expect at least 2 seconds
        between reports, and also expect that it probably doesn't take
        more than 1 second for each report to be read. We could make
        this configurable, or could dynamically adjust, such as by
        polling for input.
        """
        timer = CountdownTimer(1.0)
        while not timer.expired():
            topic, msg_obj = self._sub.receive_message(blocking=True, timeout_ms=0.05)
            if not topic:
                continue
            self._logger.debug('Received a message for topic {}', topic)
            if topic.lower() == self._cmd_topic:
                try:
                    self.handle_command(msg_obj)
                except Exception as e:
                    self._logger.error('Exception while handling command: {}', e)
                    self._logger.error('msg_obj: {}', msg_obj)

    def handle_command(self, msg):
        """Handle one relay command.

        TODO(jamessynge): Add support for 'set_relay', where we look
        up the relay name in self._last_reading to confirm that it
        exists on this device.
        """
        if msg['command'] == 'shutdown':
            self._logger.info('Received command to shutdown ArduinoIO for board {}', self.board)
            self.stop_running = True
        elif msg['command'] == 'write_line':
            line = msg['line'].rstrip('\r\n')
            self._logger.debug('Sending line to board {}: {}', self.board, line)
            line = line + '\n'
            self.write(line)
        else:
            self._logger.error('Ignoring command: {}', msg)

    def write(self, text):
        """Writes text (a string) to the port.

        Returns: the number of bytes written.
        """
        if not self._serial_data.is_connected:
            self._serial_data.connect()
        return self._serial_data.write(text)
