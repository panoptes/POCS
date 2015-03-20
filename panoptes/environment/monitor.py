import datetime
import zmq

from panoptes.utils import logger, config, messaging, threads


@logger.has_logger
@config.has_config
class EnvironmentalMonitor(object):

    """
    This is the base environmental monitor that the other monitors inherit from.
    It handles having a generic stoppable thread.

    Args:
        serial_port (str): Serial port to get readings from
    """

    def __init__(self, serial_port=None, connect_on_startup=True, name="environmental_sensor"):

        self.sleep_time = 1

        self.serial_port = serial_port

        try:
            self.serial_reader = serial.SerialData(port=self.serial_port, name=name)
        except:
            self.logger.warning("Cannot connect to environmental sensor")

        if connect_on_startup:
            try:
                self.start_monitoring()
            except:
                self.logger.warning("Problem starting serial monitor")

    def start_monitoring(self):
        """
        Connects over the serial port and starts the thread listening
        """
        self.logger.info("Starting {} monitoring".format(self.serial_reader.thread.name))

        try:
            self.serial_reader.connect()
            self.serial_reader.thread.start()
        except:
            self.logger.warning("Cannot connect to CameraEnclosure via serial port")

    def get_reading(self):
        """ Gets a reading from the sensor """
        return self.serial_reader.get_reading()

    def stop(self):
        """ Stops the running thread """
        self.logger.info("Stopping {} monitoring".format(self.serial_reader.thread.name))
        self.serial_reader.thread.stop()


    def __del__(self):
        """ Shut down the monitor """
        self.logger.info("Shutting down the monitor")
        self.stop()
