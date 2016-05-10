import os
import time
import json
import multiprocessing

from panoptes.utils.logger import get_root_logger
from panoptes.utils.config import load_config
from panoptes.utils.rs232 import SerialData
from panoptes.utils.database import PanMongo


class ArduinoSerialMonitor(object):

    """
        Monitors the serial lines and tries to parse any data recevied
        as JSON.

        Checks for the `camera_box` and `computer_box` entries in the config
        and tries to connect. Values are updated in the mongo db.
    """

    def __init__(self, sleep=2.5):

        self.logger = get_root_logger()
        self.config = load_config()

        assert 'environment' in self.config
        assert type(self.config['environment']) is dict, \
            self.logger.warning("Environment config variable not set correctly. No sensors listed")

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

        # Connect to sensors db
        self.db = PanMongo()

        self._sleep_interval = sleep

        # Setup process
        self._process = multiprocessing.Process(target=self.loop_capture)
        self._process.daemon = True

    def process_exists(self):
        if not os.path.exists('/proc/{}'.format(self._process.pid)):
            return False

        return True

    def loop_capture(self):
        """ Calls commands to be performed each time through the loop """
        while self.is_capturing and len(self.serial_readers) and True:
            sensor_data = self.get_reading()
            self.logger.debug("Inserting data to mongo: ".format(sensor_data))

            self.db.insert_current('environment', sensor_data)

            self.logger.debug("Sleeping for {} seconds".format(self._sleep_interval))
            time.sleep(self._sleep_interval)

    def start_capturing(self):
        """ Starts the capturing loop for the weather """

        self.logger.info("Staring sensors loop")
        try:
            self._process.start()
        except AssertionError:
            self.logger.info("Can't start, trying to run")
            self._process.run()
        else:
            self.is_capturing = True

    def stop_capturing(self):
        """ Stops the capturing loop for the sensors """
        self.logger.info("Stopping sensors loop")
        self.is_capturing = False

        self._process.terminate()
        self._process.join()

    @property
    def is_capturing(self):
        return self._is_capturing

    @is_capturing.setter
    def is_capturing(self, value):
        self._is_capturing = value

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
