import io
import re
import serial
import glob
from warnings import warn
from contextlib import suppress

from panoptes.pocs.focuser import AbstractFocuser
from panoptes.utils import error

# Birger adaptor serial numbers should be 5 digits
serial_number_pattern = re.compile(r'^\d{5}$')

# Error codes should be 'ERR' followed by 1-2 digits
error_pattern = re.compile(r'(?<=ERR)\d{1,2}')

error_messages = ('No error',
                  'Unrecognised command',
                  'Lens is in manual focus mode',
                  'No lens connected',
                  'Lens distance stop error',
                  'Aperture not initialised',
                  'Invalid baud rate specified',
                  'Reserved',
                  'Reserved',
                  'A bad parameter was supplied to the command',
                  'XModem timeout',
                  'XModem error',
                  'XModem unlock code incorrect',
                  'Not used',
                  'Invalid port',
                  'Licence unlock failure',
                  'Invalid licence file',
                  'Invalid library file',
                  'Reserved',
                  'Reserved',
                  'Not used',
                  'Library not ready for lens communications',
                  'Library not ready for commands',
                  'Command not licensed',
                  'Invalid focus range in memory. Try relearning the range',
                  'Distance stops not supported by the lens')


class Focuser(AbstractFocuser):
    """
    Focuser class for control of a Canon DSLR lens via a Birger Engineering Canon EF-232 adapter.

    Args:
        name (str, optional): default 'Birger Focuser'
        model (str, optional): default 'Canon EF-232'
        initial_position (int, optional): if given the focuser will drive to this encoder position
            following initialisation.
        dev_node_pattern (str, optional): Unix shell pattern to use to identify device nodes that
            may have a Birger adaptor attached. Default is '/dev/tty.USA49*.?', which is intended
            to match all the nodes created by Tripplite Keyway USA-49 USB-serial adaptors, as
            used at the time of writing by Huntsman.

    Additional positonal and keyword arguments are passed to the base class, AbstractFocuser. See
    that class' documentation for a complete list.
    """

    # Class variable to cache the device node scanning results
    _birger_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning known Birgers &
    # acts as a check against Birgers assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self,
                 name='Birger Focuser',
                 model='Canon EF-232',
                 initial_position=None,
                 dev_node_pattern='/dev/tty.USA49*.?',
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)
        self.logger.debug('Initialising Birger focuser')

        if serial_number_pattern.match(self.port):
            # Have been given a serial number
            self.logger.debug('Looking for {} ({})...'.format(self.name, self.port))

            if Focuser._birger_nodes is None:
                # No cached device nodes scanning results, need to scan.
                self.logger.debug('Getting serial numbers for all connected Birger focusers')
                Focuser._birger_nodes = {}
                # Find nodes matching pattern
                device_nodes = glob.glob(dev_node_pattern)

                # Open each device node and see if a Birger focuser answers
                for device_node in device_nodes:
                    try:
                        serial_number = self.connect(device_node)
                        Focuser._birger_nodes[serial_number] = device_node
                    except (serial.SerialException, serial.SerialTimeoutException, AssertionError):
                        # No Birger focuser on this node.
                        pass
                    finally:
                        self._serial_port.close()

                if not Focuser._birger_nodes:
                    message = 'No Birger focuser devices found!'
                    self.logger.error(message)
                    warn(message)
                    return
                else:
                    self.logger.debug('Connected Birger focusers: {}'.format(Focuser._birger_nodes))

            # Search in cached device node scanning results for serial number
            try:
                device_node = Focuser._birger_nodes[self.port]
            except KeyError:
                message = 'Could not find {} ({})!'.format(self.name, self.port)
                self.logger.error(message)
                warn(message)
                return
            self.logger.debug('Found {} ({}) on {}'.format(self.name, self.port, device_node))
            self.port = device_node

        # Check that this node hasn't already been assigned to another Birgers
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
        if initial_position is not None:
            self.position = initial_position

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
        response = self._send_command('pf', response_length=1)
        return int(response[0].rstrip())

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units.
        """
        return self._min_position

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units.
        """
        return self._max_position

    @property
    def lens_info(self):
        """
        Return basic lens info (e.g. '400mm,f28' for a 400 mm f/2.8 lens).
        """
        return self._lens_info

    @property
    def firmware_version(self):
        """
        Returns the version string of the Birger adaptor library (firmware).
        """
        return self._library_version

    @property
    def hardware_version(self):
        """
        Returns the hardware version of the Birger adaptor.
        """
        return self._hardware_version

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
            # Settings copied from Bob Abraham's birger.c
            self._serial_port = serial.Serial()
            self._serial_port.port = port
            self._serial_port.baudrate = 115200
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
        # (Birger sends '\r', not '\n'). The line_buffering option causes an automatic flush() when
        # a write contains a newline character.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           newline='\r', encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {} on {}.'.format(self.name, port))

        # Set 'verbose' and 'legacy' response modes. The response from this depends on
        # what the current mode is... but after a power cycle it should be 'rm1,0', 'OK'
        self._send_command('rm1,0', response_length=0)

        # Return serial number
        return self._send_command('sn', response_length=1)[0].rstrip()

    def move_to(self, position):
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
            response = self._send_command('fa{:d}'.format(int(position)), response_length=1)
            new_position = self._parse_move_response(response)
        finally:
            # Birger move commands block until the move is finished, so if the command has
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
            response = self._send_command('mf{:d}'.format(int(increment)), response_length=1)
            moved_by = self._parse_move_response(response)
        finally:
            # Birger move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug("Moved by {} encoder units".format(moved_by))
        return moved_by

##################################################################################################
# Private Methods
##################################################################################################

    def _send_command(self, command, response_length=None, ignore_response=False):
        """
        Sends a command to the Birger adaptor and retrieves the response.

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

        if ignore_response:
            return

        # In verbose mode adaptor will first echo the command
        echo = self._serial_io.readline().rstrip()
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

    def _parse_move_response(self, response):
        try:
            response = response[0].rstrip()
            reply = response[:4]
            amount = int(response[4:-2])
            hit_limit = bool(int(response[-1]))
            assert reply == "DONE"
        except (IndexError, AssertionError):
            raise error.PanError("{} got response '{}', expected 'DONENNNNN,N'!".format(self,
                                                                                        response))
        if hit_limit:
            self.logger.warning('{} reported hitting a focus stop'.format(self))

        return amount

    def _initialise(self):
        # Get serial number. Note, this is the serial number of the Birger adaptor,
        # *not* the attached lens (which would be more useful). Accessible as self.uid
        self._get_serial_number()

        # Get the version string of the adaptor software libray. Accessible as self.library_version
        self._get_library_version()

        # Get the hardware version of the adaptor. Accessible as self.hardware_version
        self._get_hardware_version()

        # Get basic lens info (e.g. '400mm,f28' for a 400 mm, f/2.8 lens). Accessible as
        # self.lens_info
        self._get_lens_info()

        # Initialise the aperture motor. This also has the side effect of fully opening the iris.
        self._initialise_aperture()

        # Initalise focus. First move the focus to the close stop.
        self._move_zero()

        # Then reset the focus encoder counts to 0
        self._zero_encoder()
        self._min_position = 0

        # Calibrate the focus with the 'Learn Absolute Focus Range' command
        self._learn_focus_range()

        # Finally move the focus to the far stop (close to where we'll want it) and record position
        self._max_position = self._move_inf()

        self.logger.info('{} initialised'.format(self))

    def _get_serial_number(self):
        response = self._send_command('sn', response_length=1)
        self._serial_number = response[0].rstrip()
        self.logger.debug("Got serial number {} for {} on {}".format(
            self.uid,
            self.name,
            self.port))

    def _get_library_version(self):
        response = self._send_command('lv', response_length=1)
        self._library_version = response[0].rstrip()
        self.logger.debug("Got library version '{}' for {} on {}".format(self._library_version,
                                                                         self.name,
                                                                         self.port))

    def _get_hardware_version(self):
        response = self._send_command('hv', response_length=1)
        self._hardware_version = response[0].rstrip()
        self.logger.debug("Got hardware version {} for {} on {}".format(self._hardware_version,
                                                                        self.name,
                                                                        self.port))

    def _get_lens_info(self):
        response = self._send_command('id', response_length=1)
        self._lens_info = response[0].rstrip()
        self.logger.debug("Got lens info '{}' for {} on {}".format(self._lens_info,
                                                                   self.name,
                                                                   self.port))

    def _initialise_aperture(self):
        self.logger.debug('Initialising aperture motor')
        response = self._send_command('in', response_length=1)[0].rstrip()
        if response != 'DONE':
            self.logger.error("{} got '{}', expected 'DONE'!".format(self, response))

    def _move_zero(self):
        response = self._send_command('mz', response_length=1)[0].rstrip()
        if response[:4] != 'DONE':
            self.logger.error("{} got '{}', expected 'DONENNNNN,1'!".format(self, response))
        else:
            r = response[4:].rstrip()
            self.logger.debug("Moved {} encoder units to close stop".format(r[:-2]))
            return int(r[:-2])

    def _zero_encoder(self):
        self.logger.debug('Setting focus encoder zero point')
        self._send_command('sf0', response_length=0)

    def _learn_focus_range(self):
        self.logger.debug('Learning absolute focus range')
        response = self._send_command('la', response_length=1)[0].rstrip()
        if response != 'DONE:LA':
            self.logger.error("{} got '{}', expected 'DONE:LA'!".format(self, response))

    def _move_inf(self):
        response = self._send_command('mi', response_length=1)[0].rstrip()
        if response[:4] != 'DONE':
            self.logger.error("{} got '{}', expected 'DONENNNNN,1'!".format(self, response))
        else:
            r = response[4:].rstrip()
            self.logger.debug("Moved {} encoder units to far stop".format(r[:-2]))
            return int(r[:-2])

    def _add_fits_keywords(self, header):
        header = super()._add_fits_keywords(header)
        header.set('FOC-HW', self.hardware_version, 'Focuser hardware version')
        header.set('FOC-FW', self.firmware_version, 'Focuser firmware version')
        header.set('LENSINFO', self.lens_info, 'Attached lens')
        return header
