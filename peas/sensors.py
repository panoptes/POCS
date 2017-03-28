import os
import yaml

from pocs.utils import error
from pocs.utils.database import PanMongo
from pocs.utils.logger import get_root_logger
from pocs.utils.rs232 import SerialData

from . import load_config


class ArduinoSerialMonitor(object):

    """
        Monitors the serial lines and tries to parse any data recevied
        as JSON.

        Checks for the `camera_box` and `computer_box` entries in the config
        and tries to connect. Values are updated in the mongo db.
    """

    def __init__(self, auto_detect=False, *args, **kwargs):
        self.config = load_config()
        self.logger = get_root_logger()

        assert 'environment' in self.config
        assert type(self.config['environment']) is dict, \
            self.logger.warning("Environment config variable not set correctly. No sensors listed")

        self.db = None

        # Store each serial reader
        self.serial_readers = dict()

        if auto_detect:
            for port_num in range(9):
                port = '/dev/ttyACM{}'.format(port_num)
                if os.path.exists(port):
                    self.logger.debug("Trying to connect on {}".format(port))
                    serial_reader = SerialData(port=port, threaded=False)

                    try:
                        serial_reader.connect()
                        num_tries = 5
                        while num_tries > 0:
                            self.logger.debug("Getting name on {}".format(port))
                            data = yaml.load(serial_reader.read())
                            if 'name' in data:
                                sensor = data['name']
                                num_tries = 0
                            num_tries -= 1
                    except error.BadSerialConnection:
                        continue
                    except Exception as e:
                        self.logger.warning('Could not connect to port: {}'.format(port))

                    self.serial_readers[sensor] = {
                        'reader': serial_reader,
                    }
        else:
            # Try to connect to a range of ports
            for sensor in self.config['environment'].keys():
                try:
                    port = self.config['environment'][sensor]['serial_port']
                except TypeError:
                    continue
                except KeyError:
                    continue

                if port is not None:
                    self.logger.info('Attempting to connect to serial port: {} {}'.format(sensor, port))
                    serial_reader = SerialData(port=port, threaded=True)
                    self.logger.debug(serial_reader)

                    try:
                        serial_reader.connect()
                    except Exception as e:
                        self.logger.warning('Could not connect to port: {}'.format(port))

                    self.serial_readers[sensor] = {
                        'reader': serial_reader,
                    }

    def capture(self, use_mongo=True):
        """
        Helper function to return serial sensor info.

        Reads each of the connected sensors. If a value is received, attempts
        to parse the value as json.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        sensor_data = dict()

        # Read from all the readers
        for sensor, reader_info in self.serial_readers.items():
            reader = reader_info['reader']

            # Get the values
            self.logger.debug("Reading next serial value")
            sensor_value = reader.read()

            if len(sensor_value) > 0:
                try:
                    self.logger.debug("Got sensor_value from {}".format(sensor))
                    data = yaml.load(sensor_value.replace('nan', 'null'))

                    sensor_data[sensor] = data

                except ValueError:
                    self.logger.warning("Bad JSON: {0}".format(sensor_value))
            else:
                self.logger.debug("sensor_value length is zero")

        if use_mongo:
            if self.db is None:
                self.db = PanMongo()
                self.logger.info('Connected to PanMongo')
            self.db.insert_current('environment', sensor_data)

        return sensor_data
