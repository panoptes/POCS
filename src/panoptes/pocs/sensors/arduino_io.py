# Supports reading from and writing to Arduinos attached via serial
# devices. Each line of output from the Arduinos must be a single
# JSON encoded object, one of whose fields is called "name" with the
# value the (unique) name of the board; e.g. "camera_board" or
# "telemetry_board".

from collections import deque
from contextlib import suppress

import pendulum
import serial
import threading
import traceback

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import CountdownTimer
from panoptes.utils import error
from panoptes.utils.database import PanDB


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

    def __init__(self, name, serial_device, db=None):
        """Initialize for name on device.

        Args:
            name (str): The name of the name, used as the name of the database
                table/collection to write to.
            serial_device (panoptes.utils.rs232.SerialData): The serial device instance.
            db (panoptes.utils.database.PanDB or None): The PanDB instance in
                which to record reading or None.
        """
        self.logger = get_logger()
        self.logger.info(f'Creating Arduino device with {name=} {serial_device=}')
        self.name = name.lower()
        self.serial_device = serial_device
        self.port = serial_device.port

        self.readings = deque(list(), 10)

        self._db = db or PanDB()

        # Used for reporting the first successful reading after error readings.
        self._report_next_reading = True

        self._cmd_topic = f"{self.name}:commands"
        # Using threading.Event rather than just a boolean field so that any thread
        # can get and set the keep_running property.
        self._stop_running = threading.Event()
        self.logger.success(f'Created {self}')

    def __str__(self):
        return f'{self.name} arduino ({self.port})'

    @property
    def keep_running(self):
        return not self._stop_running.is_set()

    @keep_running.setter
    def keep_running(self, value):
        """

        Args:
            value (bool): if the sensor should keep running values.
        """
        value = bool(value)
        if value is False:
            self.logger.success(f'Stopping running for {self}')
            self._stop_running.set()
        else:
            self._stop_running.clear()

    def run(self):
        """Main loop for recording data and reading commands.

        This only ends if an Exception is unhandled or if a 'shutdown'
        command is received. The most likely exception is from
        SerialData.get_and_parse_reading() in the event that the device
        disconnects from USB.
        """
        while self.keep_running:
            self.read_and_record()
            self.handle_commands()

    def read_and_record(self):
        """Try to get the next reading and, if successful, record it.

        Write the reading to the appropriate PanDB collections.

        If there is an interruption in success in reading from the device,
        we announce (log) the start and end of that situation.
        """
        reading = self.get_reading()
        if not reading:
            # TODO Consider adding an error counter.
            if not self._report_next_reading:
                self.logger.warning(f'Unable to read from {self.port}. '
                                    f'Will report next successful read.')
                self._report_next_reading = True
            return False
        if self._report_next_reading:
            self.logger.info(f'{self} {reading=}')
            self._report_next_reading = False
        self.handle_reading(reading)
        return True

    def connect(self):
        """Connect to the port."""
        with suppress(Exception):
            self.serial_device.connect()

    def disconnect(self):
        """Disconnect from the port.

        Will re-open automatically if reading or writing occurs.
        """
        try:
            self.serial_device.disconnect()
        except Exception as e:
            self.logger.error(f'Failed to disconnect from {self.port} due to: {e!r}')

    def reconnect(self):
        """Attempts a reconnection to the serial port.

        This supports handling a SerialException, such as when the USB
        bus is reset.
        """
        try:
            self.disconnect()
        except Exception as e:
            self.logger.error(f'Unable to disconnect from {self.port=}: {e!r}')
            return False

        try:
            self.connect()
            return True
        except Exception:
            self.logger.error(f'Unable to reconnect from {self.port=}: {e!r}')
            return False

    def get_reading(self, retry_limit=3, attempt_reconnect=True):
        """Reads and returns a single reading.

        If there is a connection error while attempting t r

        Args:
            retry_limit (int): The number of times to attempt to get reading.
            attempt_reconnect (bool): If there is a connection error the device
                can attempt to automatically reconnect to the port, default True.

        Returns:
            dict: The parsed reading from the device.
        """
        try:
            return self.serial_device.get_and_parse_reading(retry_limit=retry_limit)
        except serial.SerialException as e:
            self.logger.error(f'Exception raised while reading from {self}: {e!r}')
            self.logger.info(f'Exception: {traceback.format_exc()}')
            self.logger.info(f'Attempting to reconnect to {self.port=}')
            if attempt_reconnect and self.reconnect():
                self.logger.success(f'Successfully reconnected to {self.port=}')
                return self.serial_device.get_and_parse_reading(retry_limit=retry_limit)

            raise error.BadSerialConnection(e)

    def handle_reading(self, reading):
        """Saves a reading as the last_reading and writes to output_queue.

        Args:
            reading (dict): The parsed reading from the device.
        """
        timestamp, data = reading

        # Make sure the board name matches.
        if data.get('name', self.name) != self.name:
            raise error.ArduinoDataError(f'Board reports {data["name"]}, expected {self.name=}')

        reading = dict(name=self.name,
                       timestamp=pendulum.parse(timestamp).replace(tzinfo=None),
                       data=data)

        self.readings.append(reading)

        if self._db:
            self._db.insert_current(self.name, reading)

    def handle_commands(self, listen_time=1):
        """Read and process commands for set amount of time.

        Returns when there are no more commands available from the
        command subscriber, or when a second has passed.

        The interval is one (1) second by default because we expect at least two (2)
        seconds between reports, and also expect that it probably doesn't take
        more than one (1) second for each report to be read.

        Args:
            listen_time (float): The amount of time to listen for commands.
        """
        timer = CountdownTimer(1.0)
        while not timer.expired():
            topic, msg_obj = self._sub.receive_message(blocking=True, timeout_ms=0.05)
            if not topic:
                continue
            self.logger.debug('Received a message for topic {}', topic)
            if topic.lower() == self._cmd_topic:
                try:
                    self.handle_command(msg_obj)
                except Exception as e:
                    self.logger.error('Exception while handling command: {}', e)
                    self.logger.error('msg_obj: {}', msg_obj)

    def handle_command(self, msg):
        """Handle one relay command.

        TODO(jamessynge): Add support for 'set_relay', where we look
        up the relay name in self._last_reading to confirm that it
        exists on this device.
        """
        if msg['command'] == 'shutdown':
            self.logger.info('Received command to shutdown ArduinoIO for board {}', self.board)
            self.keep_running = True
        elif msg['command'] == 'write_line':
            line = msg['line'].rstrip('\r\n')
            self.logger.debug('Sending line to board {}: {}', self.board, line)
            line = line + '\n'
            self.write(line)
        else:
            self.logger.error('Ignoring command: {}', msg)

    def write(self, text):
        """Writes text (a string) to the port.

        Returns: the number of bytes written.
        """
        if not self.serial_device.is_connected:
            self.serial_device.connect()
        return self.serial_device.write(text)
