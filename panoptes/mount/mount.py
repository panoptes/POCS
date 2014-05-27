import panoptes.utils.logger as logger
import panoptes.utils.serial as serial


@logger.has_logger
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
                 serial_port=None,
                 ):
        """ 
        Create a new mount class. Sets the following properies:
        
            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self.is_connected = False
            - self.is_slewing = False
            - serial_port = /dev/ttyUSB0

        After setting, calls the following:

            - setup_seprial
            - setup_commands
        """
        assert serial_port is not None

        # We set some initial mount properties.
        self.non_sidereal_available = non_sidereal_available
        self.PEC_available = PEC_available

        # Initial states
        self.is_connected = False
        self.is_initialized = False
        self.is_slewing = False

        # Get our serial connection
        self.serial_port = serial_port

        self.create_serial()
        self.commands = self.setup_commands()

        self._pre_cmd = ''
        self._post_cmd = '#'

    def connect(self):
        """ Calls initialize then attempt to get mount version """

        if not self.is_connected:
            if not self.initialize_mount():
                self.logger.error("Cannot connect to mount")
            else:
                self.is_connected = True

        return self.is_connected

    def create_serial(self):
        """ Gets up serial connection. Defaults to serial over usb port """
        self.serial = serial.SerialData(port=self.serial_port)

    def serial_query(self, cmd):
        """ 
        Performs a send and then returns response. Will do a translate on cmd first. This should
        be the major serial utility for commands. 
        """
        self.serial_send(self.get_command(cmd))
        return self.serial_read()

    def serial_send(self, string_command):
        """ 
            Sends a string command to the mount via the serial port. First 'translates'
            the message into the form specific mount can understand
        """
        self.logger.debug("Mount Send: {}".format(string_command))
        self.serial.write(string_command)

    def serial_read(self):
        """ Sends a string command to the mount via the serial port """
        response = self.serial.read()
        self.logger.debug("Mount Read: {}".format(response))
        return response

    def get_command(self, cmd):
        """ Looks up appropriate command for telescope """
        return "{}{}{}".format(self._pre_cmd, self.commands.get(cmd), self._post_cmd)

    def setup_commands(self):
        raise NotImplementedError()

    def initialize_mount(self):
        raise NotImplementedError()

    def check_slewing(self):
        """
        Querys mount to determine if it is slewing.
        For some mounts, this is a built in function. For mount which do not have it we will have to 
        write something based on how the coordinates are changing.
        """
        # First send the command to get slewing status
        self.is_slewing = self.serial_query('slewing')
        return self.is_slewing

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

    def ping(self):
        """ Attempts to ping the mount. Can be implemented in various ways """
        raise NotImplementedError()
