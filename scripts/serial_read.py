#!/usr/bin/python3

import time
import datetime
import json
# import zmq
import pymongo

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from panoptes.utils import config, logger, serial, error


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
        for i in range(5):
            port = '/dev/ttyACM{}'.format(i)
            self.logger.info('Attempting to connect to serial port: {}'.format(port))

            serial_reader = serial.SerialData(port=port, threaded=True)

            try:
                serial_reader.connect()
                self.serial_readers[port] = serial_reader
            except:
                self.logger.debug('Could not connect to port: {}'.format(port))

        # Create the messaging socket
        # self.context = zmq.Context()
        # self.socket = self.context.socket(zmq.PUB)
        # self.socket.bind("tcp://*:6500")

        # Connect to mongo db
        self.client = pymongo.MongoClient()
        self.db = self.client.panoptes
        self.collection = self.db.sensors

        self._sleep_interval = 2

    def run(self):
        """Run by the thread, reads continuously from serial line
        """

        while True:
            for port, sensor_data in self.get_reading().items():
                self.logger.debug("{} \t {}".format(port, sensor_data))
                self.collection.insert({
                    "port": port,
                    "date": datetime.datetime.now(),
                    "data": sensor_data
                })           # Mongo
                # self.socket.send_string(sensor_string)  # ZMQ

            time.sleep(self._sleep_interval)

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
            sensor_value = reader.next().replace('nan','null')

            if len(sensor_value) > 0:
                try:
                    data = json.loads(sensor_value)

                    sensor_data[port] = data

                except ValueError:
                    print("Bad JSON: {0}".format(sensor_value))

        return sensor_data


if __name__ == "__main__":
    widget = ArduinoSerialMonitor()
    widget.run()
