#!/usr/bin/python3

import time
import datetime
import json
import matplotlib.pyplot as plt
import numpy as np
import sys

import panoptes.utils.config as config
import panoptes.utils.logger as logger
import panoptes.utils.serial as serial
import panoptes.utils.error as error

@logger.set_log_level('debug')
@logger.has_logger
@config.has_config
class ArduinoSerialMonitor(object):
    """Realtime plotting of Arduino serial sensor data"""
    def __init__(self):
        # initialize the iteration counter for scrolling window
        self.count = 0
        self.window_size = 30 # seconds of history to display

        # Hold information on sensors read
        self.sensor_readings = dict()

        # Get the class for getting data from serial sensor
        self.port = self.config.get('camera_box').get('port', '/dev/ttyACM0')
        self.serial_reader = serial.SerialData(port=self.port, threaded=True)
        self.serial_reader.connect()

        self.logger.info(self.serial_reader.read())

    def _prepare_sensor_data(self):
        """Helper function to return serial sensor info"""
        sensor_value = self.serial_reader.next()

        sensor_data = dict()
        if len(sensor_value) > 0:
            try:
                sensor_data = json.loads(sensor_value)
            except ValueError:
                print("Bad JSON: {0}".format(sensor_value))

        return sensor_data

    def get_reading(self):
        """Get the serial reading from the sensor"""
        # take the current serial sensor information
        return self._prepare_sensor_data()

    def run(self):
        """Custom timerEvent code, called at timer event receive"""

        while True:
            sensor_data = self.get_reading()
            self.logger.debug(sensor_data)
            time.sleep(2)



if __name__ == "__main__":
    widget = ArduinoSerialMonitor()
    widget.run()