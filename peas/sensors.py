import json
import os
from serial.tools.list_ports import comports as list_comports
import sys
import yaml

from pocs.utils.database import PanMongo
from pocs.utils.config import load_config
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging
from pocs.utils.rs232 import SerialData



class ArduinoSerialMonitor(object):
    """Monitors the serial lines and tries to parse any data recevied as JSON.

    Checks for the `camera_box` and `computer_box` entries in the config and tries to connect.
    Values are updated in the mongo db.
    """

    def __init__(self, auto_detect=False, *args, **kwargs):
        self.config = load_config(config_files='peas')
        self.logger = get_root_logger()

        assert 'environment' in self.config
        assert type(self.config['environment']) is dict, \
            self.logger.warning('Environment config variable not set correctly. No sensors listed')

        self.db = None
        self.messaging = None

        # Store each serial reader
        self.serial_readers = dict()

        if auto_detect or self.config['environment'].get('auto_detect', False):
            self.logger.debug('Performing auto-detect')
            for (sensor_name, serial_reader) in auto_detect_arduino_devices(logger=self.logger):
                self.logger.info('Found name "{}" on {}', sensor_name, serial_reader.name)
                self.serial_readers[sensor_name] = {
                    'reader': serial_reader,
                    'port': serial_reader.name,
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
        self.logger.debug('Attempting to connect to serial port: {}'.format(port))
        serial_reader = SerialData(port=port, baudrate=9600)
        try:
            serial_reader.connect()
            self.logger.debug('Connected to {}', port)
            return serial_reader
        except Exception as e:
            self.logger.warning('Could not connect to port: {}'.format(port))
            return None

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

        # Read from all the readers; we send messages with sensor data immediately, but accumulate
        # data from all sensors before storing in the db.
        # Note that there is no guarantee that these are the LATEST reports emitted by the sensors,
        # as the 
        sensor_data = dict()
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']

            # Get the values before attempting to re
            self.logger.debug('ArduinoSerialMonitor.capture reading sensor {}', sensor_name)
            try:
                reading = reader.get_and_parse_reading()
                if not reading:
                    self.logger.debug('Unable to get reading from {}', sensor_name)
                    continue
                self.logger.debug('Got sensor_value from {}', sensor_name)
                time_stamp, data = reading
                data['date'] = time_stamp
                sensor_data[sensor_name] = data
                if send_message:
                    self.send_message({'data': data}, channel='environment')
            except Exception as e:
                self.logger.warning('Exception while reading from sensor {}: {}', sensor_name, e)

        if use_mongo and len(sensor_data) > 0:
            if self.db is None:
                self.db = PanMongo()
                self.logger.info('Connected to PanMongo')
            self.db.insert_current('environment', sensor_data)

        return sensor_data


def auto_detect_arduino_devices(comports=None, logger=None):
    if comports is None:
        comports = find_arduino_devices()
    if not logger:
        logger = get_root_logger()
    result = []
    for port in comports:
        v = auto_detect_port(port, logger)
        if v:
            result.append(v)
    return result


def find_arduino_devices():
    """Find devices (paths or URLs) that appear to be Arduinos.

    Returns:
        a list of strings; device paths (e.g. /dev/ttyACM1) or URLs (e.g. rfc2217://host:port
        arduino_simulator://?board=camera).
    """
    comports = list_comports()
    return [p.device for p in comports if 'Arduino' in p.description]


def auto_detect_port(port, logger):
    """Open a port and determine which type of board its producing output.

    Returns: (name, serial_reader) if a recognizable device is connected, else None.
    """
    logger.debug('Attempting to connect to serial port: {}'.format(port))
    try:
        serial_reader = SerialData(port=port, baudrate=9600)
        serial_reader.connect()
        logger.debug('Connected to {}', port)
    except Exception as e:
        logger.warning('Could not connect to port: {}'.format(port))
        return None
    try:
        reading = serial_reader.get_and_parse_reading()
        if not reading:
            return None
        (ts, data) = reading
        if isinstance(data, dict) and 'name' in data and isinstance(data['name'], str):
            result = (data['name'], serial_reader)
            serial_reader = None
            return result
        logger.warning('Unable to find board name in reading: {!r}', reading)
        return None
    except Exception as e:
        logger.error('Exception while auto-detecting port {!r}: {!r}'.format(port, e))
    finally:
        if serial_reader:
            serial_reader.disconnect()


# Support testing by just listing the available devices.
if __name__ == '__main__':
    devices = find_arduino_devices()
    if devices:
        print("Arduino devices: {}".format(", ".join(devices)))
    else:
        print("No Arduino devices found.")
        sys.exit(1)
    names_and_readers = auto_detect_arduino_devices()
    for (name, serial_reader) in names_and_readers:
        print('Device {} has name {}'.format(serial_reader.name, name))
        serial_reader.disconnect()
