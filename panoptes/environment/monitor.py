import datetime
import multiprocessing

from panoptes.utils import logger, config, messaging


@logger.has_logger
@config.has_config
class EnvironmentalMonitor(object):

    """
    Sets and logs an environmental monitor

    Creates a serial data reader that is connected to a serial port and puts the
    reading of that serial line into a loop in a separate process. Also sets up a
    loop that will monitor the value on that serial line and send out a zmq message.

    Args:
        serial_port (str):          Serial port to get readings from
        name (str):                 Name for the process that runs the serial reader
        connect_on_startup(bool):   Whether monitor should start on creation, defaults to True
    """

    def __init__(self, serial_port=None, connect_on_startup=True, name="environmental_sensor"):

        self._sleep_interval = 1
        self._is_running = False

        self.serial_port = serial_port
        self.name = name

        try:
            self.serial_reader = serial.SerialData(port=self.serial_port, name=name)
        except:
            self.logger.warning("Cannot connect to environmental sensor")

        if connect_on_startup:
            try:
                self.start_monitoring()
            except:
                self.logger.warning("Problem starting serial monitor")

        self.messaging = messaging.Messaging().create_publisher()
        self.publisher = multiprocessing.Process(target=self.get_reading)
        self.publisher.start()

    def start_monitoring(self):
        """
        Connects over the serial port and starts the thread listening
        """
        self.logger.info("Starting {} monitoring".format(self.serial_reader.thread.name))

        try:
            self.serial_reader.connect()
            self.is_running(True)
            self.serial_reader.start()

        except:
            self.logger.warning("Cannot connect to monitor via serial port")

    @property
    def is_running(self):
        return self._is_running

    @is_running.setter
    def is_running(self, value):
        self._is_running = value

    def get_reading(self):
        """ Gets a reading from the sensor

        This is run as a loop, which gets the current serial reading, loads the
        value up as a JSON message, and then inserts into the mongo db. The `current`
        reading for the sensor is also updated and a message is sent out via zmq
        """
        self.logger.debug("Starting get_reading loop for {}".format(self.name))
        while True and self.is_running:

            sensor_value = self.serial_reader.get_reading()

            sensor_data = dict()
            if len(sensor_value) > 0:
                try:
                    sensor_data = json.loads(sensor_value.replace('nan', 'null'))
                except ValueError:
                    print("Bad JSON: {0}".format(sensor_value))

            # Update Mongo
            message = {
                "date": datetime.datetime.utcnow(),
                "type": self.name,
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
                    "type": self.name,
                    "data": sensor_data
                }},
                True
            )

            # Send out on ZMQ
            self.messaging.send_message(channel=self.name, message=message)

            self.logger.debug("Sleeping for {} seconds".format(self._sleep_interval))
            time.sleep(self._sleep_interval)
