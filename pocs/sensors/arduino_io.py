import copy
import threading

from pocs.utils.logger import get_root_logger
from pocs.utils import rs232


def auto_detect_arduino_devices(ports=None, logger=None):
    """Returns a list of tuples of (board_name, port)."""
    if ports is None:
        ports = list_arduino_ports()
    if not logger:
        logger = get_root_logger()
    result = []
    for port in ports:
        board_name = detect_board_on_port(port, logger)
        if board_name:
            result.append((board_name, port))
    return result


# Note: list_arduino_ports is modified by test_arduino_io.py, so if changing
# this import, the test will also need to be updated.
def list_arduino_ports():
    """Find devices (paths or URLs) that appear to be Arduinos.

    Returns:
        a list of strings; device paths (e.g. /dev/ttyACM1) or URLs (e.g. rfc2217://host:port
        arduino_simulator://?board=camera).
    """
    ports = rs232.get_serial_port_info()
    return [p.device for p in ports
            if 'arduino' in p.description.lower() or 'arduino' in p.manufacturer.lower()]


def detect_board_on_port(port, logger=None):
    """Open a port and determine which type of board its producing output.

    Returns: board_name if we can read a line of JSON from the
        port, parse it and find a 'name' attribute in the top-level object.
        Else returns None.
    """
    if not logger:
        logger = get_root_logger()
    logger.debug('Attempting to connect to serial port: {}'.format(port))
    serial_reader = None
    try:
        # First open a connection to the device.
        try:
            serial_reader = open_serial_device(port)
            if not serial_reader.is_connected:
                serial_reader.connect()
            logger.debug('Connected to {}', port)
        except Exception as e:
            logger.warning('Could not connect to port: {}'.format(port))
            return None
        try:
            reading = serial_reader.get_and_parse_reading(retry_limit=3)
            if not reading:
                return None
            (ts, data) = reading
            if isinstance(data, dict) and 'name' in data and isinstance(data['name'], str):
                return data['name']
            logger.warning('Unable to find board name in reading: {!r}', reading)
            return None
        except Exception as e:
            logger.error('Exception while auto-detecting port {!r}: {!r}'.format(port, e))
    finally:
        if serial_reader:
            serial_reader.disconnect()


def open_serial_device(port, serial_config=None, **kwargs):
    # Using a long timeout (2 times the report interval) rather than retries which can just break
    # a JSON line into two unparseable fragments.
    sd_kwargs = dict(baudrate=9600, retry_limit=1, retry_delay=0, timeout=4.0, name=port)
    if serial_config:
        sd_kwargs.update(serial_config)
    sd_kwargs.update(kwargs)
    sd_kwargs['port'] = port
    return rs232.SerialData(**sd_kwargs)


class ArduinoIO(object):
    """Reads the output from an arduino, and exposes the relays for change."""

    def __init__(self, board_name, port, output_queue, serial_config=None):
        """Inits for board on device.

        Args:
            board_name:
                The name of the board, used as the name of the database
                table/collection to write to.
            port:
                The device to connect to.
            output_queue:
                The queue to which to send the readings. Will not block
                on sending (put call), so the queue should have room for
                a few entries. By not blocking on put, we avoid dropping
                records while reading from the serial line due to dropped
                chars, and thus corrupted JSON.
            serial_config:
                The portion of the config file descibing the serial settings.
        """
        self.board_name = board_name or port
        self.port = port
        self._serial_data = open_serial_device(
            port, serial_config=serial_config, name=board_name)
        self._output_queue = output_queue
        self._logger = get_root_logger()
        self._last_reading = None

        self._serial_data_lock = threading.Lock()
        self._last_reading_lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()

    def last_reading(self):
        """Returns the last reading.

        This may be newer than the last reading in the queue if the queue was full.
        """
        with self._last_reading_lock:
            return self._last_reading

    def start_reading(self):
        if self._thread and self._thread.is_alive():
            self._logger.debug('Thread {!r} is already running with ident {!r}',
                               self._thread.name, self._thread.ident)
            return

        def reader():
            self._logger.info('Started reader thread {!r} with ident {!r}',
                              threading.current_thread().name, threading.get_ident())
            announce = False
            while not self._stop.is_set():
                reading = self._read1()
                if self._stop.is_set():
                    break
                if not reading:
                    # Consider adding an error counter.
                    announce = True
                    continue
                if announce:
                    self._logger.info('Succeeded in reading from {!r}; got:\n{!r}',
                                      self.port, reading)
                    announce = False
                self._handle_reading(reading)
            self._logger.info('Stopping reader thread {!r} with ident {!r}',
                              threading.current_thread().name, threading.get_ident())

        self._thread = threading.Thread(target=reader, name=self.board_name)
        self._thread.daemon = True
        self._thread.start()

    def stop_reading(self):
        if self._thread and self._thread.is_alive():
            self._logger.info('Waiting for thread {!r} to stop.', self._thread.name)
            self._stop.set()
            self._thread.join(timeout=4.0)
            if self._thread.is_alive():
                self._logger.error('Thread {!r} is still running.', self._thread.name)
            else:
                self._thread = None

    def write(self, text):
        with self._serial_data_lock:
            if not self._serial_data.is_connected:
                self._serial_data.connect()
            return self._serial_data.write(text)

    def disconnect(self):
        try:
            with self._serial_data_lock:
                if self._serial_data.is_connected:
                    self._serial_data.disconnect()
        except Exception as e:
            self._logger.error('Failed to disconnect from {!r} due to: {!r}', self.port, e)
            return None

    def _read1(self):
        """Reads and returns a single reading."""
        try:
            with self._serial_data_lock:
                if self._stop.is_set():
                    return None
                if not self._serial_data.is_connected:
                    self._serial_data.connect()
                reading = self._serial_data.get_and_parse_reading()
                if not reading:
                    self._logger.warning('Unable to get reading from {}', self.port)
                    return None
                return reading
        except Exception as e:
            self._logger.error('Failed to read from {!r} due to: {!r}', self.port, e)
            return None

    def _handle_reading(self, reading):
        # TODO(jamessynge): Discuss with Wilfred changing the timestamp to a datetime object
        # instead of a string. Obviously it needs to be serialized eventually.
        timestamp, data = reading
        reading = dict(timestamp=timestamp, data=data, board=self.board_name)
        with self._last_reading_lock:
            self._last_reading = copy.deepcopy(reading)
        try:
            self._output_queue.put(reading, block=False)
        except Exception as e:
            self._logger.error('output_queue.put failed for board {!r}', self.board_name)
            self._logger.error('Exception: {!r}', e)
