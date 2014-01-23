#!/usr/bin/env python

class Mount:
    """ Base class for controlling a mount """

    def __init__(self):
        """ 
        Initialize our mount class 
            - Setup serial reader
        """

        # Get the class for getting data from serial sensor
        self.serial = SerialData()

        self.is_connected = False
        self.is_slewing = False

        # Attempt to connect to serial mount
        self.connect();

    def connect(self):
        """ Connect to the mount via serial """

        # Ping our serial connection
        self.send_command(self.echo());
        ping = self.read_response();
        if ping != 'X#':
            self.logger("Connection to mount failed")

        self.is_connected = True
        return self.is_connected

    def is_connected(self):
        """ Returns is_connected state """
        
        return self.is_connected

    def send_command(self,string_command):
        """ Sends a string command to the mount via the serial port """
        self.serial.write(string_command)
        return

    def read_response(self):
        """ Sends a string command to the mount via the serial port """
        return self.serial.read()

    def is_slewing(self):
        pass

    def check_coordinates(self):
        pass

    def sync_coordinates(self):
        pass

    def slew_to_coordinates(self):
        pass

    def slew_to_park(self):
        pass

    def echo(self):
        """ mount-specific echo command """
        return "Kx" # Celestron