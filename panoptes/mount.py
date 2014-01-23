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

        self.non_sidereal_available = False
        self.PEC_available = False

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
        """ 
        Returns is_connected state 
        Sends test communication to mount to check communications.
        """
        
        return self.is_connected

    def send_command(self,string_command):
        """ Sends a string command to the mount via the serial port """
        self.serial.write(string_command)
        return

    def read_response(self):
        """ Sends a string command to the mount via the serial port """
        return self.serial.read()

    def is_slewing(self):
        """
        Querys mount to determine if it is slewing.
        For some mounts, this is a built in function. For mount which do not have it we will have to 
        write something based on how the coordinates are changing.
        """
        return self.is_slewing

    def check_coordinates(self):
        """
        Querys the mount for the current position of the mount.
        This will be useful in comparing the position of the mount to the orientation 
        indicated by the accelerometer or by an astrometric plate solve.
        """
        pass

    def sync_coordinates(self):
        """
        Takes as input, the actual coordinates (J2000) of the mount and syncs the mount on them.
        Used after a plate solve.
        Once we have a mount model, we would use sync only initially, 
        then subsequent plate solves would be used as input to the model.
        """
        pass

    def slew_to_coordinates(self):
        """
        Inputs:
            HA and Dec
            RA tracking rate (in arcsec per second, use 15.0 in absence of tracking model).
            Dec tracking rate (in arcsec per second, use 0.0 in absence of tracking model).
        """
        pass

    def slew_to_park(self):
        """
        No inputs, the park position should be defined in configuration
        """
        pass

    def echo(self):
        """ mount-specific echo command """
        return "Kx" # Celestron