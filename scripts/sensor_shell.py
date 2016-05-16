#!/usr/bin/env python
import os
import cmd
import readline
import time
from pprint import pprint
import threading
from astropy.time import Time
from astropy import units as u
from astropy.utils import console

from peas.webcam import Webcam
from peas.sensors import ArduinoSerialMonitor
from peas.weather import AAGCloudSensor

from panoptes.utils import listify
from panoptes.utils.config import load_config
from panoptes.utils.database import PanMongo


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
            elif device == 'sensors':
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

    def do_start(self, *arg):
        """ Runs all the `active_sensors`. Blocking loop for now """
        self._keep_looping = True

        for sensor_name in self.active_sensors:
            sensor = getattr(self, sensor_name)
            if hasattr(sensor, 'capture'):
                print("Doing capture for {}".format(sensor_name))
                sensor.capture()

        if self._keep_looping and len(self.active_sensors) > 0:
            self._timer = threading.Timer(self._loop_delay, self.do_start)
            print("Next reading at {}".format((Time.now() + 60 * u.second).isot))
            self._timer.start()

##################################################################################################
# Stop Methods
##################################################################################################

    def do_stop(self, *arg):
        """ Stop the loop and cancel next call """
        print("Stopping loop")
        self._keep_looping = False
        self._timer.cancel()

##################################################################################################
# Shell Methods
##################################################################################################

    def do_shell(self, line):
        """ Run a raw shell command. Can also prepend '!'. """
        print("Shell command:", line)
        output = os.popen(line).read()
        print("Shell output: ", output)
        self.last_output = output

    def emptyline(self):
        self.do_status()

    def do_exit(self, *arg):
        """ Exits PanSensorShell """
        print("Shutting down")
        self.do_stop()

        print("Bye! Thanks!")
        return True

if __name__ == '__main__':
    PanSensorShell().cmdloop()
