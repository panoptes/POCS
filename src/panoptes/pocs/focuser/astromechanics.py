import io
import serial
from warnings import warn
from contextlib import suppress

from panoptes.pocs.focuser import AbstractFocuser


class Focuser(AbstractFocuser):
    """
    Focuser class for control of a Canon DSLR lens via an Astromechanics Engineering Canon EF/EF-S adapter.

    Args:
        name (str, optional): default 'Astromechanics Focuser'
        model (str, optional): default 'Canon EF/EF-S'
        initial_position (int, optional): if given the focuser will drive to this encoder position
            following initialisation.
        dev_node_pattern (str, optional): Unix shell pattern to use to identify device nodes that
            may have a focuser adaptor attached. Default is '/dev/tty.usbserial-00*?'

    Additional positonal and keyword arguments are passed to the base class, AbstractFocuser. See
    that class' documentation for a complete list.
    """

    # Class variable to cache the device node scanning results
    _adaptor_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning known focuser adaptors and
    # acts as a check against those ones assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self,
                 name='Astromechanics Focuser Controller',
                 model='astromechanics',
                 initial_position=None,
                 dev_node_pattern='/dev/tty.usbserial-00*',
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)
        self.logger.debug('Initialising Astromechanics Lens Controller')

        # Check that this node hasn't already been assigned to another adaptor
        if self.port in Focuser._assigned_nodes:
            message = 'Device node {} already in use!'.format(self.port)
            self.logger.error(message)
            warn(message)
            return

        try:
            self.connect(self.port)
        except (serial.SerialException,
                serial.SerialTimeoutException,
                AssertionError) as err:
            message = 'Error connecting to {} on {}: {}'.format(self.name, self.port, err)
            self.logger.error(message)
            warn(message)
            return

        Focuser._assigned_nodes.append(self.port)
        self._is_moving = False
        self._initialise()

    def __del__(self):
        with suppress(AttributeError):
            device_node = self.port
            Focuser._assigned_nodes.remove(device_node)
            self.logger.debug('Removed {} from assigned nodes list'.fomat(device_node))
        with suppress(AttributeError):
            self._serial_port.close()
            self.logger.debug('Closed serial port {}'.format(self._port))

    ##################################################################################################
    # Properties
    ##################################################################################################

    @property
    def is_connected(self):
        """
        Checks status of serial port to determine if connected.
        """
        connected = False
        if self._serial_port:
            connected = self._serial_port.isOpen()
        return connected

    @AbstractFocuser.position.getter
    def position(self):
        """
        Returns current focus position in the lens focus encoder units.
        """
        response = self._send_command('P#', response_length=1)[0].replace("#", "")
        return response

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units.
        """
        return None

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units.
        """
        return None

    @property
    def is_moving(self):
        """ True if the focuser is currently moving. """
        return self._is_moving

    ##################################################################################################
    # Public Methods
    ##################################################################################################

    def connect(self, port):
        try:
            # Configure serial port.
            self._serial_port = serial.Serial()
            self._serial_port.port = port
            self._serial_port.baudrate = 38400
            self._serial_port.bytesize = serial.EIGHTBITS
            self._serial_port.parity = serial.PARITY_NONE
            self._serial_port.stopbits = serial.STOPBITS_ONE
            self._serial_port.timeout = 2.0
            self._serial_port.xonxoff = False
            self._serial_port.rtscts = False
            self._serial_port.dsrdtr = False
            self._serial_port.write_timeout = None
            self._inter_byte_timeout = None

            # Establish connection
            self._serial_port.open()

        except serial.SerialException as err:
            self._serial_port = None
            self.logger.critical('Could not open {}!'.format(port))
            raise err

        # Want to use a io.TextWrapper in order to have a readline() method with universal newlines.
        # The line_buffering option causes an automatic flush() when
        # a write contains a newline character.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           newline='\n', encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {} on {}.'.format(self.name, port))

    def move_to(self, new_position):
        """
        Moves focuser to a new position.

        Args:
            position (int): new focuser position, in encoder units

        Returns:
            int: focuser position following the move, in encoder units.

        Does not do any checking of the requested position but will warn if the lens reports
        hitting a stop.
        """
        self._is_moving = True
        try:
            self._send_command('M{:d}#'.format(int(new_position)), response_length=0)
        finally:
            # Focuser move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug("Moved to encoder position {}".format(new_position))
        return new_position

    def move_by(self, increment):
        """
        Move focuser by a given amount.

        Args:
            increment (int): distance to move the focuser, in encoder units.

        Returns:
            int: distance moved, in encoder units.

        Does not do any checking of the requested increment but will warn if the lens reports
        hitting a stop.
        """
        self._is_moving = True
        try:
            ini_pos = self.position
            new_pos = int(ini_pos) + increment
            self._send_command('M{:d}#'.format(int(new_pos)), response_length=0)
        finally:
            # Focuser move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug("Moved by {} encoder units. Current position is {}".format(increment, new_pos))
        return new_pos

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def _send_command(self, command, response_length=None):
        """
        Sends a command to the Focuser adaptor and retrieves the response.

        Args:
            command (string): command string to send (without newline), e.g. "P#"
            response length (integer, optional, default=None): number of lines of response expected.
                For most commands this should be 0 or 1. If None readlines() will be called to
                capture all responses. As this will block until the timeout expires it should only
                be used if the number of lines expected is not known (e.g. 'ds' command).

        Returns:
            list: possibly empty list containing the '\n' terminated lines of the response from the
                adaptor.
        """
        if not self.is_connected:
            self.logger.critical("Attempt to send command to {} when not connected!".format(self))
            return

        # Clear the input buffer in case there's anything left over in there.
        self._serial_port.reset_input_buffer()

        # Send command
        self._serial_io.write(command + '\n')

        # Depending on which command was sent there may or may not be any further
        # response.
        response = []

        if response_length == 0:
            # Not expecting any further response. Should check the buffer anyway in case an error
            # message has been sent.
            if self._serial_port.in_waiting:
                response.append(self._serial_io.readline())

        elif response_length > 0:
            # Expecting some number of lines of response. Attempt to read that many lines.
            for i in range(response_length):
                response.append(self._serial_io.readline())

        else:
            # Don't know what to expect. Call readlines() to get whatever is there.
            response.append(self._serial_io.readlines())

        return response

    def _initialise(self):
        self._is_moving = True
        try:
            # Get initial position of focuser adaptor.
            self.logger.debug(f'Initial position of focuser is at {self.position} encoder units')

            # Initialise the aperture motor. This also has the side effect of fully opening the iris.
            self._initialise_aperture()
            self.logger.info('{} initialised'.format(self))

        finally:
            self._is_moving = False

    def _initialise_aperture(self):
        self.logger.debug('Initialising aperture motor')
        self._send_command('A00#', response_length=0)
        self.logger.debug('Aperture initialised at maximum value')
