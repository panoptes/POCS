#!/usr/bin/env python
import cmd
import readline

from peas.webcams import Webcams
from peas.monitors import ArduinoSerialMonitor


class PanSensorShell(cmd.Cmd):
    """ A simple command loop for the sensors. """
    intro = 'Welcome to PanSenorShell! Type ? for help'
    prompt = 'PanSensors > '
    webcams = None
    sensors = None
    weather = None
    weather_device = '/dev/ttyUSB1'

    def do_status(self, *arg):
        """ Get the entire system status and print it pretty like! """
        pass
        # print("Status: ")

    def do_load_webcams(self, *arg):
        """ Load the webcams """
        print("Loading webcams")
        self.webcams = Webcams()

    def do_load_sensors(self, *arg):
        """ Load the arduino environment sensors """
        print("Loading sensors")
        self.sensors = ArduinoSerialMonitor()

    def do_load_weather(self, *arg):
        """ Load the weather reader """
        print("Loading weather")
        self.weather = AAGCloudSensor(serial_address=self.weather_device)
        self.sensors = ArduinoSerialMonitor()

    def do_start_webcams(self, *arg):
        """ Starts the webcams looping """
        if self.webcams is None:
            self.do_load_webcams()

        if self.webcams is not None:
            print("Starting webcam capture")
            self.webcams.start_capturing()

    def do_start_sensors(self, *arg):
        """ Starts environmental sensor monitoring """
        if self.sensors is None:
            self.do_load_sensors()

        if self.sensors is not None:
            print("Starting sensors capture")
            self.sensors.start_capturing()

    def do_stop_webcams(self, *arg):
        """ Stops webcams """
        print("Stopping webcam capture")
        if self.webcams.processes_exist():
            self.webcams.stop_capturing()

    def emptyline(self):
        self.do_status()

    def do_exit(self, *arg):
        """ Exits PanSensorShell """
        print("Shutting down")
        if self.webcams is not None:
            self.do_stop_webcams()

        print("Bye! Thanks!")
        return True

if __name__ == '__main__':
    PanSensorShell().cmdloop()
