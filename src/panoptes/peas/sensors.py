from collections import deque

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.database import PanDB
from panoptes.utils.rs232 import SerialData


class ArduinoSerialMonitor(object):
    """Monitors an arduino device on the serial line and parses any data received as JSON.

    """
    logger = get_logger()

    def __init__(self, sensor_name=None, sensor_port=None, db_type=None, *args, **kwargs):
        self.name = sensor_name
        self.port = sensor_port

        # Setup database.
        self.db = None
        db_type = db_type or get_config('db.type', default='file')
        self.db = PanDB(db_type=db_type)

        self.serial_reader = self.connect(sensor_port)

        # Queue of the last ten items.
        self.readings = deque(list(), 10)

    @property
    def last_reading(self):
        """The last item that was read from the Arduino.

        Returns:
            dict or None: The parsed reading from the Arduino or None.
        """
        try:
            return self.readings[-1]
        except IndexError:
            return None

    def capture(self, store_result=True, separate_power=True):
        """Capture the data from the serial device to the readings queue.

        Args:
            store_result (bool): If the result should be stored or just written
                to logs, default True.

        Returns:
            dict: The parsed data from the serial device.
        """
        self.logger.debug(f'Reading {self.name} on {self.port}')

        try:
            time_stamp, data = self.serial_reader.get_and_parse_reading()
            if not data:
                self.logger.debug(f'Unable to get reading from {self.name=}')

            data['date'] = time_stamp
            self.logger.debug(f'{self.name}: {data=}')

            # Add to the queue.
            self.readings.append(data)

            if store_result:
                self.db.insert_current(self.name, data)

                # Make a separate power entry
                if separate_power and 'power' in data:
                    self.db.insert_current('power', data['power'])

        except Exception as e:
            self.logger.warning(f'Exception while reading from {self.name=}: {e!r}')

    def connect(self, port):
        """Connect to the serial device on the given port.

        Args:
            port (str): The serial port to connect.

        Returns:
            panoptes.utils.serial.SerialData: The connected SerialData instance.
        """
        self.logger.info(f'Connecting to {port=}')
        try:
            self.serial_reader = SerialData(port=port, baudrate=9600)
            self.serial_reader.connect()
        except (error.BadSerialConnection, Exception) as e:
            self.logger.warning(f'Could not connect to {port=}: {e!r}')

        self.logger.success(f'Connected to {port}')

    def disconnect(self):
        """Disconnect the serial device."""
        self.serial_reader.stop()
