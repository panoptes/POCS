#!/usr/bin/env python
import os
import cmd
import readline

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
    sensors = None
    weather = None
    weather_device = '/dev/ttyUSB1'
    db = PanMongo()

    config = load_config()

##################################################################################################
# Generic Methods
##################################################################################################

    def do_status(self, *arg):
        """ Get the entire system status and print it pretty like! """
        print("Running Systems:")
        print("\tWeather: {}".format(self.weather and self.weather.process.is_alive()))
        print("\tSensors: {}".format(self.sensors and self.sensors.process.is_alive()))

        if self.webcams:
            for webcam in self.webcams:
                print("\tWebcam {}: {}".format(webcam.name, webcam.process.is_alive()))
        else:
            print("\tWebcams: None")

    def do_last_reading(self, device):
        """ Gets the last reading from the device. """
        if hasattr(self, device):
            print("{}:".format(device.upper()))

            if device == 'weather':
                print(self.db.current.find_one({'type': 'weather'}))
            elif device == 'sensors':
                print(self.db.current.find_one({'type': 'environment'}))


##################################################################################################
# Load Methods
##################################################################################################

    def do_load_webcams(self, *arg):
        """ Load the webcams """
        print("Loading webcams")

        self.webcams = list()

        for webcam in self.config.get('webcams', []):
            self.webcams.append(Webcam(webcam))

    def do_load_sensors(self, *arg):
        """ Load the arduino environment sensors """
        print("Loading sensors")
        self.sensors = ArduinoSerialMonitor()

    def do_load_weather(self, *arg):
        """ Load the weather reader """
        print("Loading weather")
        self.weather = AAGCloudSensor(serial_address=self.weather_device)

##################################################################################################
# Start Methods
##################################################################################################

    def do_start_webcams(self, *arg):
        """ Starts the webcams looping """
        if self.webcams is None:
            self.do_load_webcams()

        if self.webcams is not None:
            for webcam in self.webcams:
                print("Starting {} webcam capture".format(webcam.name))
                webcam.start_capturing()

    def do_start_sensors(self, *arg):
        """ Starts environmental sensor monitoring """
        if self.sensors is None:
            self.do_load_sensors()

        if self.sensors is not None:
            print("Starting sensors capture")
            self.sensors.start_capturing()

    def do_start_weather(self, *arg):
        """ Starts reading weather station """
        if self.weather is None:
            self.do_load_weather()

        if self.weather is not None and self.weather.AAG:
            print("Starting weather capture")
            self.weather.start_capturing()
        else:
            print("Not connected to weather")

##################################################################################################
# Stop Methods
##################################################################################################

    def do_stop_webcams(self, *arg):
        """ Stops webcams """
        for webcam in self.webcams:
            if webcam.process.is_alive():
                print("Stopping {} webcam capture".format(webcam.name))
                webcam.stop_capturing()

    def do_stop_weather(self, *arg):
        """ Stops reading weather """
        print("Stopping weather capture")
        if self.weather.process.is_alive():
            self.weather.stop_capturing()

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
        if self.webcams is not None:
            self.do_stop_webcams()

        if self.weather is not None:
            self.do_stop_weather()

        print("Bye! Thanks!")
        return True

if __name__ == '__main__':
    PanSensorShell().cmdloop()
