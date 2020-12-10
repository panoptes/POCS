import io
import serial
import re
from warnings import warn
from contextlib import suppress

from panoptes.pocs.focuser import AbstractFocuser


class AbstractSerialFocuser(AbstractFocuser):

    # Class variable to cache the device node scanning results
    _adaptor_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning
    # known focuser devices & acts as a check against adaptors assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self, *args, **kwargs):
        """Initialize an AbstractSerialMount for the port defined in the config.
            Opens a connection to the serial device, if it is valid.
        """

        super().__init__(*args, **kwargs)

        # Check that this node hasn't already been assigned to another focuser device
        if self.port in AbstractSerialFocuser._assigned_nodes:
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

        AbstractSerialFocuser._assigned_nodes.append(self.port)
        self._is_moving = False
        self._initialise()

    def __del__(self):
        with suppress(AttributeError):
            device_node = self.port
            AbstractSerialFocuser._assigned_nodes.remove(device_node)
            self.logger.debug(f'Removed {device_node} from assigned nodes list')
        with suppress(AttributeError):
            self._serial_port.close()
            self.logger.debug(f'Closed serial port {self._port}')

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

    @property
    def is_moving(self):
        """ True if the focuser is currently moving. """
        return self._is_moving

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def _connect(self, port, baudrate):
        try:
            # Configure serial port.
            self._serial_port = serial.Serial()
            self._serial_port.port = port
            self._serial_port.baudrate = baudrate
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

        # Want to use a io.TextWrapper in order to have a readline() method with universal newlines
        # (focuser adaptors usually send '\r', not '\n'). The line_buffering option causes an automatic flush() when
        # a write contains a newline character.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           newline='\r', encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {} on {}.'.format(self.name, port))

    def _send_command(self, command, response_length=None, error_pattern=None, error_messages=[]):
        """
        Sends a command to the focuser adaptor and retrieves the response.

        Args:
            command (string): command string to send (without newline), e.g. 'fa1000', 'pf'
            response length (integer, optional, default=None): number of lines of response expected.
                For most commands this should be 0 or 1. If None readlines() will be called to
                capture all responses. As this will block until the timeout expires it should only
                be used if the number of lines expected is not known (e.g. 'ds' command).

        Returns:
            list: possibly empty list containing the '\r' terminated lines of the response from the
                adaptor.
        """
        if not self.is_connected:
            self.logger.critical("Attempt to send command to {} when not connected!".format(self))
            return

        # Clear the input buffer in case there's anything left over in there.
        self._serial_port.reset_input_buffer()

        # Send command
        self._serial_io.write(command + '\r')

        response = self._serial_io.readline()
        if self.model == "astromechanics":
            return response

        # In verbose mode adaptor will first echo the command
        echo = response.rstrip()
        assert echo == command, self.logger.warning("echo != command: {} != {}".format(
            echo, command))

        # Adaptor should then send 'OK', even if there was an error.
        ok = self._serial_io.readline().rstrip()
        assert ok == 'OK'

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

        # Check for an error message in response
        if response:
            # Not an empty list.
            error_match = error_pattern.match(response[0])
            if error_match:
                # Got an error message! Translate it.
                try:
                    error_message = error_messages[int(error_match.group())]
                    self.logger.error("{} returned error message '{}'!".format(
                        self, error_message))
                except Exception:
                    self.logger.error("Unknown error '{}' from {}!".format(
                        error_match.group(), self))

        return response
