#!/usr/bin/env python
import os
import cmd
import readline
from pprint import pprint

from peas.webcam import Webcam
from peas.sensors import ArduinoSerialMonitor
from peas.weather import AAGCloudSensor

from panoptes.utils import listify
from panoptes.utils.config import load_config
from panoptes.utils.database import PanMongo
from panoptes.utils.process import PanProcess


class PanSensorShell(cmd.Cmd):
    """ A simple command loop for the sensors. """
    intro = 'Welcome to PanSensorShell! Type ? for help'
    prompt = 'PanSensors > '
    webcams = None
    sensors = None
    weather = None
    weather_device = '/dev/ttyUSB1'
    processes = dict()
    db = PanMongo()

    config = load_config()

##################################################################################################
# Generic Methods
##################################################################################################

    def do_status(self, *arg):
        """ Get the entire system status and print it pretty like! """
        print("Running Systems:")
        for proc_type, procs in self.processes.items():
            for proc in listify(procs):
                print("\t{}: {}".format(proc_type.upper(), proc.process.is_alive()))

    def do_last_reading(self, device):
        """ Gets the last reading from the device. """
        if hasattr(self, device):
            print("{}:".format(device.upper()))

            rec = None
            if device == 'weather':
                rec = self.db.current.find_one({'type': 'weather'})
            elif device == 'sensors':
                rec = self.db.current.find_one({'type': 'environment'})
            pprint(rec)


##################################################################################################
# Load Methods
##################################################################################################

    def do_load_webcams(self, *arg):
        """ Load the webcams """
        print("Loading webcams")

        self.webcams = list()
        procs = list()

        for webcam in self.config.get('webcams', []):
            # Create the webcam
            wc = Webcam(webcam)

            # Create the process
            wc_process = PanProcess(name='{}Proc'.format(webcam.get('name')), target_method=wc.loop_capture)

            self.webcams.append(wc)
            procs.append(wc_process)

        self.processes['webcams'] = procs

    def do_load_sensors(self, *arg):
        """ Load the arduino environment sensors """
        print("Loading sensors")
        self.sensors = ArduinoSerialMonitor()
        self.processes['sensors'] = PanProcess(name='SensorsProc', target_method=self.sensors.loop_capture)

    def do_load_weather(self, *arg):
        """ Load the weather reader """
        print("Loading weather")
        self.weather = AAGCloudSensor(serial_address=self.weather_device)
        self.processes['weather'] = PanProcess(name='WeatherProc', target_method=self.weather.loop_capture)

##################################################################################################
# Start Methods
##################################################################################################

    def do_start_webcams(self, *arg):
        """ Starts the webcams looping """
        if self.webcams is None:
            self.do_load_webcams()

        if 'webcams' in self.processes:
            for webcam_proc in self.processes['webcams']:
                print("Stopping {} webcam capture".format(webcam_proc.name))
                webcam_proc.start_capturing()

    def do_start_sensors(self, *arg):
        """ Starts environmental sensor monitoring """
        if self.sensors is None:
            self.do_load_sensors()

        if 'sensors' in self.processes:
            print("Starting sensors capture")
            self.processes['sensors'].start_capturing()

    def do_start_weather(self, *arg):
        """ Starts reading weather station """
        if self.weather is None:
            self.do_load_weather()

        if 'weather' in self.processes and self.weather.AAG:
            print("Starting weather capture")
            self.processes['weather'].start_capturing()
        else:
            print("Not connected to weather")

##################################################################################################
# Stop Methods
##################################################################################################

    def do_stop_webcams(self, *arg):
        """ Stops webcams """
        if 'webcams' in self.processes:
            for webcam_proc in self.processes['webcams']:
                if webcam_proc.process.is_alive():
                    print("Stopping {} webcam capture".format(webcam_proc.name))
                    webcam_proc.stop_capturing()

    def do_stop_weather(self, *arg):
        """ Stops reading weather """
        if 'weather' in self.processes and self.processes['weather'].process.is_alive():
            print("Stopping weather capture")
            self.processes['weather'].stop_capturing()

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
