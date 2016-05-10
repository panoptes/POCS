#!/usr/bin/python3

import sys
import time
import json

from panoptes.utils.logger import get_logger
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

        self.logger = get_logger(self)
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

    def run(self):
        """
        The actual method that is run for each thread. Loops over each connected sensor
        and reads from the serial line.
        """

        try:
            while True and len(self.serial_readers):
                sensor_data = self.get_reading()
                self.logger.debug("Inserting data to mongo: ".format(sensor_data))

                self.db.insert_current('environment', sensor_data)

                self.logger.debug("Sleeping for {} seconds".format(self._sleep_interval))
                time.sleep(self._sleep_interval)

        except KeyboardInterrupt:
            self.logger.info("Shutting down serial reader")
        finally:
            self.logger.info("Loop finished. (No sensors connected?)")

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


if __name__ == "__main__":
    monitor = ArduinoSerialMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Shutting down")
        sys.exit(0)
