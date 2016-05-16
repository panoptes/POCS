#!/usr/bin/env python
import os
import cmd
import readline
from pprint import pprint
from threading import Timer
from astropy.time import Time
from astropy import units as u

from peas.webcam import Webcam
from peas.sensors import ArduinoSerialMonitor
from peas.weather import AAGCloudSensor

from pocs.utils.config import load_config
from pocs.utils.database import PanMongo


class PanSensorShell(cmd.Cmd):
    """ A simple command loop for the sensors. """
    intro = 'Welcome to PanSensorShell! Type ? for help'
    prompt = 'PanSensors > '
    webcams = None
    environment = None
    weather = None
    weather_device = '/dev/ttyUSB1'
    active_sensors = list()
    db = PanMongo()
    _keep_looping = False
    _loop_delay = 60
    _timer = None
    verbose = False

    config = load_config()

##################################################################################################
# Generic Methods
##################################################################################################

    def do_status(self, *arg):
        """ Get the entire system status and print it pretty like! """
        pass

    def do_last_reading(self, device):
        """ Gets the last reading from the device. """
        if hasattr(self, device):
            print('*' * 80)
            print("{}:".format(device.upper()))

            rec = None
            if device == 'weather':
                rec = self.db.current.find_one({'type': 'weather'})
            elif device == 'environment':
                rec = self.db.current.find_one({'type': 'environment'})

            pprint(rec)
            print('*' * 80)

    def do_enable_sensor(self, sensor):
        """ Enable the given sensor """
        if hasattr(self, sensor) and sensor not in self.active_sensors:
            self.active_sensors.append(sensor)

    def do_disable_sensor(self, sensor):
        """ Enable the given sensor """
        if hasattr(self, sensor) and sensor in self.active_sensors:
            self.active_sensors.remove(sensor)

    def do_set_verbose(self, arg):
        """ Sets the `verbose` flag. """
        if type(arg) == bool:
            self.verbose = arg

##################################################################################################
# Load Methods
##################################################################################################

    def do_load_all(self, *arg):
        print("Starting all systems")
        self.do_load_weather()
        self.do_load_environment()
        self.do_load_webcams()

    def do_load_webcams(self, *arg):
        """ Load the webcams """
        print("Loading webcams")

        class WebCams(object):
            def __init__(self, config):

                self.webcams = list()
                self.config = config

                for webcam in self.config:
                    # Create the webcam
                    if os.path.exists(webcam.get('port')):
                        self.webcams.append(Webcam(webcam))

            def capture(self):
                for wc in self.webcams:
                    wc.capture()

        self.webcams = WebCams(self.config.get('webcams', []))

        self.do_enable_sensor('webcams')

    def do_load_environment(self, *arg):
        """ Load the arduino environment sensors """
        print("Loading sensors")
        self.environment = ArduinoSerialMonitor()
        self.do_enable_sensor('environment')

    def do_load_weather(self, *arg):
        """ Load the weather reader """
        print("Loading weather")
        self.weather = AAGCloudSensor(serial_address=self.weather_device)
        self.do_enable_sensor('weather')

##################################################################################################
# Start Methods
##################################################################################################

    def _loop(self, *arg):
        for sensor_name in self.active_sensors:
            if self._keep_looping:
                sensor = getattr(self, sensor_name)
                if hasattr(sensor, 'capture'):
                    if self.verbose:
                        print("Doing capture for {}".format(sensor_name))
                    sensor.capture()

        self._setup_timer(method=self._loop)

    def do_start(self, *arg):
        """ Runs all the `active_sensors`. Blocking loop for now """
        self._keep_looping = True

        if self.verbose:
            print("Starting sensors")

        self._setup_timer(method=self._loop)

    def _setup_timer(self, method=None, delay=None):
        if self._keep_looping and len(self.active_sensors) > 0:

            if not delay:
                delay = self._loop_delay

            self._timer = Timer(delay, method)

            if self.verbose:
                print("Next reading at {}".format((Time.now() + delay * u.second).isot))

            self._timer.start()

##################################################################################################
# Stop Methods
##################################################################################################

    def do_stop(self, *arg):
        """ Stop the loop and cancel next call """
        if self.verbose:
            print("Stopping loop")

        self._keep_looping = False

        if self._timer:
            self._timer.cancel()

##################################################################################################
# Shell Methods
##################################################################################################

    def do_shell(self, line):
        """ Run a raw shell command. Can also prepend '!'. """
        if self.verbose:
            print("Shell command:", line)

        output = os.popen(line).read()

        if self.verbose:
            print("Shell output: ", output)

        self.last_output = output

    def emptyline(self):
        self.do_status()

    def do_exit(self, *arg):
        """ Exits PanSensorShell """
        print("Shutting down")
        self.do_stop()

        print("Please be patient and allow for process to finish. Thanks! Bye!")
        return True

if __name__ == '__main__':
    PanSensorShell().cmdloop()
