#!/usr/bin/python3

import time
import datetime
import json
import zmq

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from panoptes.utils import config, logger, serial, error

@logger.set_log_level(level='debug')
@logger.has_logger
@config.has_config
class ArduinoSerialMonitor(object):
    """Realtime plotting of Arduino serial sensor data"""
    def __init__(self):

        # Get the class for getting data from serial sensor
        self.port = self.config.get('camera_box').get('port', '/dev/ttyACM0')
        self.serial_reader = serial.SerialData(port=self.port, threaded=True)
        self.serial_reader.connect()

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:6500")

        self.sensor_value = None

        self._sleep_interval = 2

        self.logger.info(self.serial_reader.read())

    def _prepare_sensor_data(self):
        """Helper function to return serial sensor info"""
        self.sensor_value = self.serial_reader.next()

        sensor_data = dict()
        if len(self.sensor_value) > 0:
            try:
                sensor_data = json.loads(self.sensor_value)
            except ValueError:
                print("Bad JSON: {0}".format(self.sensor_value))

        return sensor_data

    def get_reading(self):
        """Get the serial reading from the sensor"""
        # take the current serial sensor information
        return self._prepare_sensor_data()

    def run(self):
        """Reads continuously from arduino, """

        while True:
            sensor_data = self.get_reading()

            for key, value in sensor_data.items():
                sensor_string = '{} {}'.format(key, value)
                self.socket.send_string(sensor_string)

            time.sleep(self._sleep_interval)


if __name__ == "__main__":
    widget = ArduinoSerialMonitor()
    widget.run()