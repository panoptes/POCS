import panoptes.utils.logger as logger
import panoptes.utils.serial as serial


class AbstractMount:

    """ 
    Abstract Base class for controlling a mount 
 
    Methods to be implemented:
        - setup_commands
        - get_command
        - check_coordinates
        - sync_coordinates
        - slew_to_coordinates
        - slew_to_park
        - echo

    """

    def __init__(self,
                 connect=False,
                 non_sidereal_available=False,
                 PEC_available=False,
                 serial_port='/dev/ttyACM0',
                 log=None,
                 ):
        """ 
        Create a new mount class. Sets the following properies:
        
            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self.is_connected = False
            - self.is_slewing = False
            - serial_port = /dev/ttyACM0

        After setting, calls the following:

            - setup_serial
            - setup_commands
        """
        self.logger = log or logger.Logger()

        # We set some initial mount properties and then call initialize_mount
        # so that specific mounts can override
        self.non_sidereal_available = non_sidereal_available
        self.PEC_available = PEC_available

        self.is_connected = False
        self.is_slewing = False

        self.serial_port = '/dev/ttyACM0'  # USB to serial port

        # Get our serial connection
        self.serial = serial_port

        self.setup_serial()
        self.commands = self.setup_commands()

    def setup_serial(self):
        """ Gets up serial connection. Defaults to serial over usb port """
        self.serial = serial.SerialData(
            port=self.serial_port, logger=self.logger)

    def setup_commands(self):
        raise NotImplementedError()

    def connect(self):
        """ Connect to the mount via serial """

        # Ping our serial connection
        self.serial_send(self.echo())
        ping = self.serial_read()
        if ping != 'X#':
            self.logger.error("Connection to mount failed")
        else:
            self.is_connected = True

        return self.is_connected

    def is_connected(self):
        """ 
        Returns is_connected state 
        Sends test communication to mount to check communications.
        """

        return self.is_connected

    def serial_send(self, string_command):
        """ 
            Sends a string command to the mount via the serial port. First 'translates'
            the message into the form specific mount can understand
        """
        translated = self.translate_command(string_command)
        self.serial.write(translated)
        return

    def serial_read(self):
        """ Sends a string command to the mount via the serial port """
        return self.serial.read()

    def serial_query(self, cmd='echo'):
        """ Performs a send and then returns response. Will do a translate on cmd first """
        self.serial_send(self.get_command(cmd))
        return self.serial_read()

    def check_slewing(self):
        """
        Querys mount to determine if it is slewing.
        For some mounts, this is a built in function. For mount which do not have it we will have to 
        write something based on how the coordinates are changing.
        """
        # First send the command to get slewing status
        self.is_slewing = self.serial_query('slewing')
        return self.is_slewing

    def get_command(self,cmd=None):
        """ Looks up appropriate command for telescope """
        return self.commands.get(cmd)

    def check_coordinates(self):
        """
        Querys the mount for the current position of the mount.
        This will be useful in comparing the position of the mount to the orientation 
        indicated by the accelerometer or by an astrometric plate solve.
        """
        raise NotImplementedError()

    def sync_coordinates(self):
        """
        Takes as input, the actual coordinates (J2000) of the mount and syncs the mount on them.
        Used after a plate solve.
        Once we have a mount model, we would use sync only initially, 
        then subsequent plate solves would be used as input to the model.
        """
        raise NotImplementedError()

    def slew_to_coordinates(self):
        """
        Inputs:
            HA and Dec
            RA tracking rate (in arcsec per second, use 15.0 in absence of tracking model).
            Dec tracking rate (in arcsec per second, use 0.0 in absence of tracking model).
        """
        raise NotImplementedError()

    def slew_to_park(self):
        """
        No inputs, the park position should be defined in configuration
        """
        raise NotImplementedError()

    def echo(self):
        """ mount-specific echo command """
        raise NotImplementedError()
