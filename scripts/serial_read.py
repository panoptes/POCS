#!/usr/bin/python3

import time
import datetime
import json
import bson.json_util as json_util
import pymongo

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from panoptes.utils import config, logger, serial, error, database

@logger.set_log_level(level='debug')
@logger.has_logger
@config.has_config
class ArduinoSerialMonitor(object):

    """
        Monitors the serial lines and tries to parse any data recevied
        as JSON. This script first checks the first five ttyACM nodes and
        tries to connect. Also connects to our mongo instance to update values
    """

    def __init__(self):

        # Store each serial reader
        self.serial_readers = dict()

        # Try to connect to a range of ports
        for i in range(2):
            port = '/dev/arduino_{}'.format(i)
            self.logger.info('Attempting to connect to serial port: {}'.format(port))

            serial_reader = serial.SerialData(port=port, threaded=True)

            try:
                serial_reader.connect()
                self.serial_readers[port] = serial_reader
            except:
                self.logger.warning('Could not connect to port: {}'.format(port))

        # Connect to sensors db
        self.sensors = database.PanMongo().sensors

        self._sleep_interval = 1

    def run(self):
        """Run by the thread, reads continuously from serial line
        """

        try:
            while True:
                sensor_data = self.get_reading()
                self.logger.debug("sensor_data: {}".format(sensor_data))

                message = {
                    "date": datetime.datetime.utcnow(),
                    "type": "environment",
                    "data": sensor_data
                }

                # Mongo insert
                self.logger.debug("Inserting data to mongo")
                self.sensors.insert(message)

                # Update the 'current' reading
                self.logger.debug("Updating the 'current' value in mongo")
                self.sensors.update(
                    {"status": "current"},
                    {"$set": {
                         "date": datetime.datetime.utcnow(),
                         "type": "environment",
                         "data": sensor_data
                        }
                    },
                    True
                )

                self.logger.debug("Sleeping for {} seconds".format(self._sleep_interval))
                time.sleep(self._sleep_interval)

        except KeyboardInterrupt:
            self.logger.info("Shutting down serial reader")

    def get_reading(self):
        """
        Convenience method to get the sensor data.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by port. port->values
        """
        # take the current serial sensor information
        return self._prepare_sensor_data()

    def _prepare_sensor_data(self):
        """
        Helper function to return serial sensor info.

        Reads each of the connected sensors. If a value is received, attempts
        to parse the value as json.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by port. port->values
        """

        sensor_data = dict()

        # Read from all the readers
        for port, reader in self.serial_readers.items():

            # Get the values
            self.logger.debug("Reading next serial value")
            sensor_value = reader.next()

            if len(sensor_value) > 0:
                try:
                    self.logger.debug("Got sensor_value from {}".format(port))
                    data = json.loads(sensor_value.replace('nan', 'null'))

                    sensor_data[port] = data

                except ValueError:
                    self.logger.warning("Bad JSON: {0}".format(sensor_value))
            else:
                self.logger.debug("sensor_value length is zero")

        return sensor_data


if __name__ == "__main__":
    monitor = ArduinoSerialMonitor()
    monitor.run()
