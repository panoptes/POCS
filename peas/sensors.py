import time
import json

from panoptes.utils.rs232 import SerialData
from panoptes.utils.database import PanMongo
from panoptes.utils.config import load_config
from panoptes.utils.logger import get_root_logger


class ArduinoSerialMonitor(object):
    """
        Monitors the serial lines and tries to parse any data recevied
        as JSON.

        Checks for the `camera_box` and `computer_box` entries in the config
        and tries to connect. Values are updated in the mongo db.
    """

    def __init__(self, loop_delay=5):
        self.config = load_config()
        self.logger = get_root_logger()

        assert 'environment' in self.config
        assert type(self.config['environment']) is dict, \
            self.logger.warning("Environment config variable not set correctly. No sensors listed")

        self.db = None
        self._loop_delay = loop_delay

        # Store each serial reader
        self.serial_readers = dict()

        # Try to connect to a range of ports
        for sensor in self.config['environment'].keys():
            port = self.config['environment'][sensor].get('serial_port', None)
            self.logger.info('Attempting to connect to serial port: {} {}'.format(sensor, port))

            if port is not None:
                serial_reader = SerialData(port=port, threaded=True)

                try:
                    serial_reader.connect()
                    self.serial_readers[sensor] = serial_reader
                except:
                    self.logger.warning('Could not connect to port: {}'.format(port))

    def loop_capture(self):
        """ Calls commands to be performed each time through the loop """
        while True:
            if self.db is None:
                self.db = PanMongo()
                self.logger.info('Connected to PanMongo')
            else:
                data = self.get_reading()
                self.db.insert_current('environment', data)

            time.sleep(self._loop_delay)

    def get_reading(self):
        """
        Helper function to return serial sensor info.

        Reads each of the connected sensors. If a value is received, attempts
        to parse the value as json.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        sensor_data = dict()

        # Read from all the readers
        for sensor, reader in self.serial_readers.items():

            # Get the values
            self.logger.debug("Reading next serial value")
            sensor_value = reader.read()

            if len(sensor_value) > 0:
                try:
                    self.logger.debug("Got sensor_value from {}".format(sensor))
                    data = json.loads(sensor_value.replace('nan', 'null'))

                    sensor_data[sensor] = data

                except ValueError:
                    self.logger.warning("Bad JSON: {0}".format(sensor_value))
            else:
                self.logger.debug("sensor_value length is zero")

        return sensor_data
