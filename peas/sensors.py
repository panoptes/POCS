import os
import yaml

from pocs.utils.database import PanMongo
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging
from pocs.utils.rs232 import SerialData

from pocs.utils.config import load_config


class ArduinoSerialMonitor(object):

    """
        Monitors the serial lines and tries to parse any data recevied
        as JSON.

        Checks for the `camera_box` and `computer_box` entries in the config
        and tries to connect. Values are updated in the mongo db.
    """

    def __init__(self, auto_detect=False, *args, **kwargs):
        self.config = load_config(config_files='peas')
        self.logger = get_root_logger()

        assert 'environment' in self.config
        assert type(self.config['environment']) is dict, \
            self.logger.warning("Environment config variable not set correctly. No sensors listed")

        self.db = None
        self.messaging = None

        # Store each serial reader
        self.serial_readers = dict()

        if auto_detect:
            for port_num in range(9):
                port = '/dev/ttyACM{}'.format(port_num)
                if os.path.exists(port):
                    self.logger.debug("Trying to connect on {}".format(port))

                    sensor_name = None
                    serial_reader = self._connect_serial(port)

                    num_tries = 5
                    self.logger.debug("Getting name on {}".format(port))
                    while num_tries > 0:
                        try:
                            data = serial_reader.get_reading()
                        except yaml.parser.ParserError:
                            pass
                        except AttributeError:
                            pass
                        else:
                            try:
                                if 'name' in data:
                                    sensor_name = data['name']
                                    num_tries = 0
                            except Exception as e:
                                self.logger.warning("Read on serial: {}".format(e))
                        num_tries -= 1

                    if sensor_name is not None:
                        self.serial_readers[sensor_name] = {
                            'reader': serial_reader,
                        }
        else:
            # Try to connect to a range of ports
            for sensor_name in self.config['environment'].keys():
                try:
                    port = self.config['environment'][sensor_name]['serial_port']
                except TypeError:
                    continue
                except KeyError:
                    continue

                serial_reader = self._connect_serial(port)
                self.serial_readers[sensor_name] = {
                    'reader': serial_reader,
                    'port': port,
                }

    def _connect_serial(self, port):
        if port is not None:
            self.logger.debug('Attempting to connect to serial port: {}'.format(port))
            serial_reader = SerialData(port=port)
            self.logger.debug(serial_reader)

            try:
                serial_reader.connect()
                serial_reader.start()
            except Exception as e:
                self.logger.warning('Could not connect to port: {}'.format(port))

            return serial_reader

    def disconnect(self):
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']
            reader.stop()

    def send_message(self, msg, channel='environment'):
        if self.messaging is None:
            self.messaging = PanMessaging.create_publisher(6510)

        self.messaging.send_message(channel, msg)

    def capture(self, use_mongo=True, send_message=True):
        """
        Helper function to return serial sensor info.

        Reads each of the connected sensors. If a value is received, attempts
        to parse the value as json.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        sensor_data = dict()

        # Read from all the readers
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']

            # Get the values
            self.logger.debug("Reading next serial value")
            try:
                sensor_info = reader.get_reading()
            except IndexError:
                continue

            time_stamp = sensor_info[0]
            sensor_value = sensor_info[1]
            try:
                self.logger.debug("Got sensor_value from {}".format(sensor_name))
                data = yaml.load(sensor_value.replace('nan', 'null'))
                data['date'] = time_stamp

                sensor_data[sensor_name] = data

                if send_message:
                    self.send_message({'data': data}, channel='environment')
            except yaml.parser.ParserError:
                self.logger.warning("Bad JSON: {0}".format(sensor_value))
            except ValueError:
                self.logger.warning("Bad JSON: {0}".format(sensor_value))
            except TypeError:
                self.logger.warning("Bad JSON: {0}".format(sensor_value))
            except Exception as e:
                self.logger.warning("Bad JSON: {0}".format(sensor_value))

            if use_mongo and len(sensor_data) > 0:
                if self.db is None:
                    self.db = PanMongo()
                    self.logger.info('Connected to PanMongo')
                self.db.insert_current('environment', sensor_data)
        else:
            self.logger.debug("No sensor data received")

        return sensor_data
