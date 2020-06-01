#!/usr/bin/env python

import os
import cmd
import datetime
import readline
import sys

from pytz import utc
from astropy.utils import console
from threading import Timer
from pprint import pprint

from panoptes.peas.sensors import ArduinoSerialMonitor
from panoptes.peas.remote_sensors import RemoteMonitor

from panoptes.utils.config.client import get_config
from panoptes.utils import current_time
from panoptes.utils.database import PanDB


class PanSensorShell(cmd.Cmd):

    """ A simple command loop for the sensors. """
    intro = 'Welcome to PEAS Shell! Type ? for help'
    prompt = 'PEAS > '
    weather = None
    control_board = None
    control_env_board = None
    camera_board = None
    camera_env_board = None
    active_sensors = dict()
    db = PanDB(db_type=get_config('db.type', default='file'))
    _keep_looping = False
    _loop_delay = 60
    _timer = None
    captured_data = list()

    telemetry_relay_lookup = {
        'computer': {'pin': 8, 'board': 'telemetry_board'},
        'fan': {'pin': 6, 'board': 'telemetry_board'},
        'camera_box': {'pin': 7, 'board': 'telemetry_board'},
        'weather': {'pin': 5, 'board': 'telemetry_board'},
        'mount': {'pin': 4, 'board': 'telemetry_board'},
        'cam_0': {'pin': 5, 'board': 'camera_board'},
        'cam_1': {'pin': 6, 'board': 'camera_board'},
    }

    # NOTE: These are not pins but zero-based index numbers.
    controlboard_relay_lookup = {
        'computer': {'pin': 0, 'board': 'control_board'},
        'mount': {'pin': 1, 'board': 'control_board'},
        'camera_box': {'pin': 2, 'board': 'control_board'},
        'weather': {'pin': 3, 'board': 'control_board'},
        'fan': {'pin': 4, 'board': 'control_board'},
    }


##################################################################################################
# Generic Methods
##################################################################################################

    def do_status(self, *arg):
        """ Get the entire system status and print it pretty like! """
        if self._keep_looping:
            console.color_print("{:>12s}: ".format('Loop Timer'),
                                "default", "active", "lightgreen")
        else:
            console.color_print("{:>12s}: ".format('Loop Timer'),
                                "default", "inactive", "yellow")

        for sensor_name in ['control_board', 'camera_board', 'weather']:
            if sensor_name in self.active_sensors:
                console.color_print("{:>12s}: ".format(sensor_name.title()),
                                    "default", "active", "lightgreen")
            else:
                console.color_print("{:>12s}: ".format(sensor_name.title()),
                                    "default", "inactive", "yellow")

    def do_last_reading(self, device):
        """ Gets the last reading from the device. """
        if not device:
            print_warning('Usage: last_reading <device>')
            return
        if not hasattr(self, device):
            print_warning('No such sensor: {!r}'.format(device))
            return

        rec = self.db.get_current(device)

        if rec is None:
            print_warning('No reading found for {!r}'.format(device))
            return

        print_info('*' * 80)
        print("{}:".format(device.upper()))
        pprint(rec)
        print_info('*' * 80)

        # Display the age in seconds of the record
        if isinstance(rec.get('date'), datetime.datetime):
            now = current_time(datetime=True).astimezone(utc)
            record_date = rec['date'].astimezone(utc)
            age = (now - record_date).total_seconds()
            if age < 120:
                print_info('{:.1f} seconds old'.format(age))
            else:
                print_info('{:.1f} minutes old'.format(age / 60.0))

    def complete_last_reading(self, text, line, begidx, endidx):
        """Provide completions for sensor names."""
        names = list(self.active_sensors.keys())
        return [name for name in names if name.startswith(text)]

    def do_enable_sensor(self, sensor, delay=None):
        """ Enable the given sensor """
        if delay is None:
            delay = self._loop_delay

        if hasattr(self, sensor) and sensor not in self.active_sensors:
            self.active_sensors[sensor] = {'reader': sensor, 'delay': delay}

    def do_disable_sensor(self, sensor):
        """ Disable the given sensor """
        if hasattr(self, sensor) and sensor in self.active_sensors:
            del self.active_sensors[sensor]

    def do_toggle_debug(self, sensor):
        """ Toggle DEBUG on/off for sensor

        Arguments:
            sensor {str} -- environment, weather
        """
        # TODO(jamessynge): We currently use a single logger, not one per module or sensor.
        # Figure out whether to keep this code and make it work, or get rid of it.
        import logging
        get_level = {
            logging.DEBUG: logging.INFO,
            logging.INFO: logging.DEBUG,
        }

        if hasattr(self, sensor):
            try:
                log = getattr(self, sensor).logger
                log.setLevel(get_level[log.getEffectiveLevel()])
            except Exception:
                print_error("Can't change log level for {}".format(sensor))

    def complete_toggle_debug(self, text, line, begidx, endidx):
        """Provide completions for toggling debug logging."""
        names = list(self.active_sensors.keys())
        return [name for name in names if name.startswith(text)]

##################################################################################################
# Load Methods
##################################################################################################

    def do_load_all(self, *arg):
        """Load the weather and environment sensors."""
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return
        self.do_load_weather()
        self.do_load_control_board()
        self.do_load_camera_board()

    def do_load_control_board(self, *arg):
        """ Load the arduino control_board sensors """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return
        print("Loading control board sensor")
        self.control_board = ArduinoSerialMonitor(
            sensor_name='control_board', db_type=get_config('db.type', default='file'))
        self.do_enable_sensor('control_board', delay=10)

    def do_load_camera_board(self, *arg):
        """ Load the arduino camera_board sensors """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return
        print("Loading camera board sensor")
        self.camera_board = ArduinoSerialMonitor(
            sensor_name='camera_board', db_type=get_config('db.type', default='file'))
        self.do_enable_sensor('camera_board', delay=10)

    def do_load_control_env_board(self, *arg):
        """ Load the arduino control_board sensors """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return
        print("Loading control box environment board sensor")
        endpoint_url = get_config('environment.control_env_board.url')
        self.control_env_board = RemoteMonitor(endpoint_url=endpoint_url,
                                               sensor_name='control_env_board',
                                               db_type=get_config('db.type', default='file')
                                               )
        self.do_enable_sensor('control_env_board', delay=10)

    def do_load_camera_env_board(self, *arg):
        """ Load the arduino control_board sensors """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return
        print("Loading camera box environment board sensor")
        endpoint_url = get_config('environment.camera_env_board.url')
        self.camera_env_board = RemoteMonitor(endpoint_url=endpoint_url,
                                              sensor_name='camera_env_board',
                                              db_type=get_config('db.type', default='file')
                                              )
        self.do_enable_sensor('camera_env_board', delay=10)

    def do_load_weather(self, *arg):
        """ Load the weather reader """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return

        print("Loading weather reader endpoint")
        endpoint_url = get_config('environment.weather.url')
        self.weather = RemoteMonitor(endpoint_url=endpoint_url,
                                     sensor_name='weather',
                                     db_type=get_config('db.type', default='file')
                                     )
        self.do_enable_sensor('weather', delay=60)


##################################################################################################
# Relay Methods
##################################################################################################

    def do_turn_off_relay(self, *arg):
        """Turn on relay.

        The argument should be the name of the relay, i.e. on of:

            * fan
            * mount
            * weather
            * camera_box

        The names must correspond to the entries in the lookup tables above.
        """
        relay = arg[0]

        if hasattr(self, 'control_board'):
            relay_lookup = self.controlboard_relay_lookup
        else:
            relay_lookup = self.telemetry_relay_lookup

        try:
            relay_info = relay_lookup[relay]
            serial_connection = self.control_board.serial_readers[relay_info['board']]['reader']

            serial_connection.ser.reset_input_buffer()
            serial_connection.write("{},0\n".format(relay_info['pin']))
        except Exception as e:
            print_warning(f"Problem turning relay off {relay} {e!r}")
            print_warning(e)

    def do_turn_on_relay(self, *arg):
        """Turn off relay.

        The argument should be the name of the relay, i.e. on of:

            * fan
            * mount
            * weather
            * camera_box

        The names must correspond to the entries in the lookup tables above.
    """
        relay = arg[0]

        if hasattr(self, 'control_board'):
            relay_lookup = self.controlboard_relay_lookup
        else:
            relay_lookup = self.telemetry_relay_lookup

        try:
            relay_info = relay_lookup[relay]
            serial_connection = self.control_board.serial_readers[relay_info['board']]['reader']

            serial_connection.ser.reset_input_buffer()
            serial_connection.write("{},1\n".format(relay_info['pin']))
        except Exception as e:
            print_warning(f"Problem turning relay off {relay} {e!r}")
            print_warning(e)

    def complete_turn_off_relay(self, text, line, begidx, endidx):
        """Provide completions for relay names."""
        if hasattr(self, 'control_board'):
            names = ['camera_box', 'fan', 'mount', 'weather']
        else:
            names = ['cam_0', 'cam_1', 'camera_box', 'fan', 'mount', 'weather']
        return [name for name in names if name.startswith(text)]

    def complete_turn_on_relay(self, text, line, begidx, endidx):
        """Provide completions for relay names."""
        if hasattr(self, 'control_board'):
            names = ['camera_box', 'fan', 'mount', 'weather']
        else:
            names = ['cam_0', 'cam_1', 'camera_box', 'fan', 'mount', 'weather']
        return [name for name in names if name.startswith(text)]

    def do_toggle_computer(self, *arg):
        """Toggle the computer relay off and then on again after 30 seconds.

        Note:

            The time delay is set on the arduino and is blocking.
        """
        relay = 'computer'

        if hasattr(self, 'control_board'):
            relay_lookup = self.controlboard_relay_lookup
        else:
            relay_lookup = self.telemetry_relay_lookup

        try:
            relay_info = relay_lookup[relay]
            serial_connection = self.control_board.serial_readers[relay_info['board']]['reader']

            serial_connection.ser.reset_input_buffer()
            serial_connection.write("{},9\n".format(relay_info['pin']))
        except Exception as e:
            print_warning(f"Problem toggling computer: {e!r}")
            print_warning(e)

##################################################################################################
# Start/Stop Methods
##################################################################################################

    def do_start(self, *arg):
        """ Runs all the `active_sensors`. Blocking loop for now """
        if self._keep_looping:
            print_error('The timer loop is already running.')
            return

        self._keep_looping = True

        print_info("Starting sensors")

        self._loop()

    def do_stop(self, *arg):
        """ Stop the loop and cancel next call """
        # NOTE: We don't yet have a way to clear _timer.
        if not self._keep_looping and not self._timer:
            print_error('The timer loop is not running.')
            return

        print_info("Stopping loop")

        self._keep_looping = False

        if self._timer:
            self._timer.cancel()

    def do_change_delay(self, *arg):
        """Change the timing between reads from the named sensor."""
        # NOTE: For at least the Arduinos, we should not need a delay and a timer, but
        # simply a separate thread, reading from the board as data is available.
        # We might use a delay to deal with the case where the device is off-line
        # but we want to periodically check if it becomes available.
        parts = None
        if len(arg) == 1:
            parts = arg[0].split()
        if parts is None or len(parts) != 2:
            print_error('Expected a sensor name and a delay, not "{}"'.format(' '.join(arg)))
            return
        sensor_name, delay = parts
        try:
            delay = float(delay)
            if delay <= 0:
                raise ValueError()
        except ValueError:
            print_warning("Not a positive number: {!r}".format(delay))
            return
        try:
            print_info("Changing sensor {} to a {} second delay".format(sensor_name, delay))
            self.active_sensors[sensor_name]['delay'] = delay
        except KeyError:
            print_warning("Sensor not active: {!r}".format(sensor_name))

##################################################################################################
# Shell Methods
##################################################################################################

    def do_shell(self, line):
        """ Run a raw shell command. Can also prepend '!'. """
        print("Shell command:", line)

        output = os.popen(line).read()

        print_info("Shell output: ", output)

        self.last_output = output

    def emptyline(self):
        self.do_status()

    def do_exit(self, *arg):
        """ Exits PEAS Shell """
        print("Shutting down")
        if self._timer or self._keep_looping:
            self.do_stop()

        print("Please be patient and allow for process to finish. Thanks! Bye!")
        return True

##################################################################################################
# Private Methods
##################################################################################################

    def _capture_data(self, sensor_name):
        # We are missing a Mutex here for accessing these from active_sensors and
        # self.
        if sensor_name in self.active_sensors:
            sensor = getattr(self, sensor_name)
            try:
                sensor.capture(store_result=True)
            except Exception as e:
                print_warning(f'Problem storing captured data: {e!r}')

            self._setup_timer(sensor_name, delay=self.active_sensors[sensor_name]['delay'])

    def _loop(self, *arg):
        for sensor_name in self.active_sensors.keys():
            self._capture_data(sensor_name)

    def _setup_timer(self, sensor_name, delay=None):
        if self._keep_looping and len(self.active_sensors) > 0:

            if not delay:
                delay = self._loop_delay

            # WARNING: It appears we have a single _timer attribute, but we create
            # one Timer for each active sensor (i.e. environment and weather).
            self._timer = Timer(delay, self._capture_data, args=(sensor_name,))

            self._timer.start()

##################################################################################################
# Utility Methods
##################################################################################################


def print_info(msg):
    console.color_print(msg, 'lightgreen')


def print_warning(msg):
    console.color_print(msg, 'yellow')


def print_error(msg):
    console.color_print(msg, 'red')


if __name__ == '__main__':
    invoked_script = os.path.basename(sys.argv[0])
    histfile = os.path.expanduser('~/.{}_history'.format(invoked_script))
    histfile_size = 1000
    if os.path.exists(histfile):
        readline.read_history_file(histfile)

    PanSensorShell().cmdloop()

    readline.set_history_length(histfile_size)
    readline.write_history_file(histfile)
