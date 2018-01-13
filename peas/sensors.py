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
            for port_num in range(9):
                port = '/dev/ttyACM{}'.format(port_num)
                result = self._auto_detect_port(port)
                if result is not None:
                    (sensor_name, serial_reader) = result
                    self.logger.info('Found name "{}" on {}', sensor_name, port)
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

    def _auto_detect_port(self, port):
        """Determines the type of Arduino attached to the port.

        Returns: tuple of (sensor_name, serial_reader) if able to determine a name,
            else returns None.
        """
        if os.path.exists(port):
            self.logger.debug('Port {} exists', port)
        elif '://' in port:
            self.logger.debug('Port {} may have a PySerial handler installed; testing.', port)
        else:
            self.logger.debug('Port {} not found', port)
            return None
        try:
            serial_reader = self._connect_serial(port)
            if serial_reader is None:
                return None
        except Exception:
            self.logger.debug('Failed to connect on {}', port)
            return None
        # Try to get a reading with a full line. Sometimes the first line is
        # partial, so we need to read a second line to find a line with the
        # name of the board in the reading.
        num_tries = 5
        for _ in range(num_tries):
            try:
                self.logger.debug('Reading from {}', port)
                data = self._get_parsed_reading(serial_reader)
                if data and len(data) == 2 and 'name' in data[1]:
                    parsed = data[1]
                    sensor_name = parsed['name']
                    self.logger.debug('Found name {}', sensor_name)
                    result = (sensor_name, serial_reader)
                    serial_reader = None
                    return result
                self.logger.debug("'name' not found in reading")
            except Exception:
                pass
            finally:
                if serial_reader:
                    serial_reader.disconnect()
        return None

    def _connect_serial(self, port):
        self.logger.debug('Attempting to connect to serial port: {}'.format(port))
        serial_reader = SerialData(port=port)
        try:
            serial_reader.connect()
            self.logger.debug('Connected to {}', port)
            return serial_reader
        except Exception as e:
            self.logger.warning('Could not connect to port: {}'.format(port))
            return None

    def _get_parsed_reading(self, serial_reader):
        try:
            data = serial_reader.get_reading()
        except Exception as e:
            self.logger.debug('get_reading failed: %r', e)
            return None
        try:
            self.logger.debug('Parsing the reading from {}', serial_reader.name)
            parsed = json.loads(data[1])
            return (data[0], parsed)
        except Exception as e:
            self.logger.debug('Failed to parse reading: %r', e)
            self.logger.debug('Erroneous reading: %r', data)
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

        sensor_data = dict()

        # Read from all the readers
        for sensor_name, reader_info in self.serial_readers.items():
            reader = reader_info['reader']

            # Get the values
            self.logger.debug('Reading next serial value')
            try:
                sensor_info = reader.get_reading()
            except IndexError:
                continue

            time_stamp = sensor_info[0]
            sensor_value = sensor_info[1]
            try:
                self.logger.debug('Got sensor_value from {}'.format(sensor_name))
                data = yaml.load(sensor_value.replace('nan', 'null'))
                data['date'] = time_stamp

                sensor_data[sensor_name] = data

                if send_message:
                    self.send_message({'data': data}, channel='environment')
            except yaml.parser.ParserError:
                self.logger.warning('Bad JSON: {0}'.format(sensor_value))
            except ValueError:
                self.logger.warning('Bad JSON: {0}'.format(sensor_value))
            except TypeError:
                self.logger.warning('Bad JSON: {0}'.format(sensor_value))
            except Exception as e:
                self.logger.warning('Bad JSON: {0}'.format(sensor_value))

            if use_mongo and len(sensor_data) > 0:
                if self.db is None:
                    self.db = PanMongo()
                    self.logger.info('Connected to PanMongo')
                self.db.insert_current('environment', sensor_data)
        else:
            self.logger.debug('No sensor data received')

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
        serial_reader = SerialData(port=port)
        serial_reader.connect()
        logger.debug('Connected to {}', port)
    except Exception as e:
        logger.warning('Could not connect to port: {}'.format(port))
        return None
    try:
        reading = get_and_parse_reading(serial_reader, logger=logger)
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



def get_and_parse_reading(serial_reader, logger=None, num_tries=5):
    """Try several times to get a parseable reading, which is then returned.

    Usually when we open a serial port connected to one of the PANOPTES arduino sketches we find
    a partial line of output when we first start reading, which then fails to be parsed. This
    function reads several times until we get a full reading.

    Returns: (timestamp, parsed_reading), where timestamp is a datetime.datetime and parsed_reading
        is the parsed version of the reading (i.e. the decoded JSON data).
    """
    if not logger:
        logger = serial_reader.logger
    for try_num in range(num_tries):
        try:
            logger.debug('Reading from {} (try_num={})', serial_reader.name, try_num)
            raw_reading = serial_reader.get_reading()
        except Exception as e:
            logger.warning('get_reading failed: %r', e)
            continue
        reading = parse_reading(raw_reading, logger)
        if reading:
            logger.debug('Parsed reading: {}', reading)
            return reading
        # Don't emit a warning for the first reading.
        if try_num > 0:
            logger.warning('On try_num {}, JSON parsing failed for {!r}', try_num, raw_reading)
    return None


def parse_reading(reading, logger):
    if not reading:
        return None
    ts, data = reading
    try:
        parsed = json.loads(data)
        return (ts, parsed)
    except Exception as e:
        logger.debug('Exception while parsing JSON: %r', e)
        logger.debug('Erroneous JSON: %r', data)
        return None


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
