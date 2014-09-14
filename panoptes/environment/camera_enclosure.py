import datetime
import zmq

from panoptes.utils import logger, config, messaging, threads, serial

@logger.has_logger
@config.has_config
class CameraEnclosure(object):
    """
    Listens to the sensors inside the camera enclosure

    Args:
        messaging (panoptes.messaging.Messaging): A messaging Object for creating new
            sockets.
    """
    def __init__(self, messaging=None):

        if messaging is None:
            messaging = messaging.Messaging()

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


    def start_publishing(self):
        """Reads continuously from arduino, """

        while not self.thread.is_stopped():
            sensor_data = self.get_reading()

            for key, value in sensor_data.items():
                sensor_string = '{} {}'.format(key, value)
                self.socket.send_string(sensor_string)

            self.thread.wait(self.sleep_time)


    def stop(self):
        """ Stops the running thread """
        self.thread.stop()

if __name__ == '__main__':
    enclosure = CameraEnclosure()
    enclosure.run()