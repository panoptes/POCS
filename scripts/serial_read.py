#!/usr/bin/python3

import time
import datetime
import json
import zmq
import pymongo
from pymongo import MongoClient

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from panoptes.utils import config, logger, serial, error

@logger.set_log_level(level='debug')
@logger.has_logger
@config.has_config
class ArduinoSerialMonitor(object):
    """Realtime plotting of Arduino serial sensor data"""
    def __init__(self):

        self.serial_readers = dict()

        # Try to connect to a range of ports
        for i in range(5):
            port = '/dev/ttyACM{}'.format(i)
            self.logger.info('Attempting to connecto serial port: {}'.format(port))

            serial_reader = serial.SerialData(port=port, threaded=True)

            try:
                serial_reader.connect()
                self.serial_readers[port] = serial_reader
            except:
                self.logger.debug('Could not connect to port: {}'.format(port))

        # Create the messaging socket
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:6500")

        # Connect to mongo db
        self.client = MongoClient()
        self.db = self.client.panoptes
        self.collection = self.db.sensors

        self.sensor_value = None

        self._sleep_interval = 2

    def _prepare_sensor_data(self):
        """Helper function to return serial sensor info"""

        sensor_data = list()

        # Read from all the readers
        for port, reader in self.serial_readers.items():
            # Get the values
            sensor_value = reader.next()

            if len(sensor_value) > 0:
                try:
                    data = json.loads(sensor_value)

                    sensor_data.append(data)

                except ValueError:
                    print("Bad JSON: {0}".format(sensor_value))

        return { key: value for (key, value) in data.items() for data in sensor_data }

    def get_reading(self):
        """Get the serial reading from the sensor"""
        # take the current serial sensor information
        return self._prepare_sensor_data()

    def run(self):
        """Reads continuously from arduino, """

        while True:
            for key, sensor_data in self.get_reading().items():
                # for key, value in sensor_data.items():
                    sensor_string = '{} {}'.format(key, sensor_data)

                    print("\n\n {}".format(sensor_string))                    # Terminal
                    # self.collection.insert(sensor_data)           # Mongo
                    # self.socket.send_string(sensor_string)  # ZMQ

            time.sleep(self._sleep_interval)


if __name__ == "__main__":
    widget = ArduinoSerialMonitor()
    widget.run()