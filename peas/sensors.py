
# Note: list_comports is modified by test_sensors.py, so if changing
# this import, the test will also need to be updated.
from serial.tools.list_ports import comports as list_comports

import sys

from pocs.utils.database import PanDB
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
        except Exception:
            self.logger.warning('Could not connect to port: {}'.format(port))
            return None

    def disconnect(self):
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']
            reader.stop()

    def send_message(self, msg, topic='environment'):
        if self.messaging is None:
            self.messaging = PanMessaging.create_publisher(6510)

        self.messaging.send_message(topic, msg)

    def capture(self, store_result=True, send_message=True):
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
        # as the OS or PySerial object may have a backlog, and especially because we are reading
        # these in lock step; if one produces a report every 1.9 seconds, and the other every 2.1
        # seconds, then we will generally wait an extra 0.2 seconds on each loop relative to the
        # rate at which the fast one is producing output, For this reason, we really need to split
        # these into two separate threads and probably two seperate Mongo collections (e.g. not
        # 'environment' but 'camera_board' and 'telemetry_board').
        sensor_data = dict()
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']

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
                    self.send_message({'data': data}, topic='environment')

                # Make a separate power entry
                if 'power' in data:
                    self.db.insert_current('power', data['power'])

            except Exception as e:
                self.logger.warning('Exception while reading from sensor {}: {}', sensor_name, e)

        if store_result and len(sensor_data) > 0:
            if self.db is None:
                self.db = PanDB()
            self.db.insert_current('environment', sensor_data)

        return sensor_data


def auto_detect_arduino_devices(comports=None, logger=None):
    if comports is None:
        comports = find_arduino_devices()
    if not logger:
        logger = get_root_logger()
    result = []
    for port in comports:
        v = detect_board_on_port(port, logger)
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


def detect_board_on_port(port, logger=None):
    """Open a port and determine which type of board its producing output.

    Returns: (name, serial_reader) if we can read a line of JSON from the
        port, parse it and find a 'name' attribute in the top-level object.
        Else returns None.
    """
    if not logger:
        logger = get_root_logger()
    logger.debug('Attempting to connect to serial port: {}'.format(port))
    try:
        serial_reader = SerialData(port=port, baudrate=9600, retry_limit=1, retry_delay=0)
        if not serial_reader.is_connected:
            serial_reader.connect()
        logger.debug('Connected to {}', port)
    except Exception:
        logger.warning('Could not connect to port: {}'.format(port))
        return None
    try:
        reading = serial_reader.get_and_parse_reading(retry_limit=3)
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
