import datetime
import zmq
import json

from . import monitor
from panoptes.utils import logger, config, messaging, threads, serial


@logger.has_logger
@config.has_config
class CameraEnclosure(monitor.EnvironmentalMonitor):

    """
    Listens to the sensors inside the camera enclosure

    Args:
        messaging (panoptes.messaging.Messaging): A messaging Object for creating new
            sockets.
    """

    def __init__(self, serial_port, connect_on_startup=False):
        super().__init__(messaging=messaging, name='CameraEnclosure')

        # Get the class for getting data from serial sensor
        self.serial_port = serial_port

        try:
            self.serial_reader = serial.SerialData(port=self.serial_port, threaded=True)
        except:
            self.logger.warning("Cannot connect to environmental sensor")

        if connect_on_startup:
            try:
                self.serial_reader.connect()
            except:
                self.logger.warning("Cannot connect to CameraEnclosure via serial port")

            try:
                self.start_monitoring()
            except:
                self.logger.warning("Problem starting serial monitor")

    def monitor(self):
        """ Gets the next reading from the sensors in the camera enclosure """

        sensor_data = self.get_reading()
        self.logger.debug("camera_box: {}".format(sensor_data))

        for key, value in sensor_data.items():
            sensor_string = '{} {}'.format(key, value)
            self.send_message(sensor_string)

    def get_reading(self):
        """Get the serial reading from the sensor"""
        # take the current serial sensor information
        return self._prepare_sensor_data()

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
