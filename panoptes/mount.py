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

        # Attempt to connect to serial mount
        self.connect();

    def connect():
        """ Connect to the mount via serial """

        # Ping our serial connection
        self.send_command(self.echo());
        ping = self.read_response();
        if ping != 'X#':
            self.logger("Connection to mount failed")

    def send_command(string_command):
        """ Sends a string command to the mount via the serial port """
        self.serial.write(string_command)
        return

    def read_response():
        """ Sends a string command to the mount via the serial port """
        return self.serial.read()

    def echo():
        """ mount-specific echo command """
        return "Kx" # Celestron
