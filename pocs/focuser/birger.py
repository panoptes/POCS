import io
import re
import serial

from pocs.focuser.focuser import AbstractFocuser


class Focuser(AbstractFocuser):

    """
    Focuser class for control of a Canon DSLR lens via a Birger Engineering Canon EF-232 adapter
    """

    def __init__(self,
                 name='Birger Focuser',
                 model='Canon EF-232',
                 initial_position=None,
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)
        self.logger.debug('Initialising Birger focuser')
        self.connect()
        if initial_position:
            self.position = initial_position

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
        Returns current focus position in the lens focus encoder units
        """
        response = self._send_command('pf', response_length=1)
        return int(response[0].rstrip())

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units
        """
        return self._min_position

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units
        """
        return self._max_position

##################################################################################################
# Public Methods
##################################################################################################

    def connect(self):
        try:
            # Configure serial port.
            # Settings copied from Bob Abraham's birger.c
            self._serial_port = serial.Serial()
            self._serial_port.port = self.port
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
            self.logger.critical('Could not connect to {}!'.format(self))
            raise err

        # Want to use a io.TextWrapper in order to have a readline() method with universal newlines
        # (Birger sends '\r', not '\n'). The line_buffering option causes an automatic flush() when
        # a write contains a newline character.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           newline='\r', encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {} on {}.'.format(self.name, self.port))

        # Set 'verbose' and 'legacy' response modes. The response from this depends on
        # what the current mode is... but after a power cycle it should be 'rm1,0', 'OK'
        try:
            self._send_command('rm1,0', response_length=0)
        except AssertionError as err:
            self.logger.critical('Error communicating with {} on {}!'.format(self.name, self.port))
            raise err

        # Get serial number. Note, this is the serial number of the Birger adaptor,
        # *not* the attached lens (which would be more useful).
        self._get_serial_number()

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

        self.logger.info('\t\t\t {} initialised'.format(self))

    def move_to(self, position):
        """
        Move the focus to a specific position in lens encoder units.
        Does not do any checking of the requested position but will warn if the lens reports hitting a stop.
        Returns the actual position moved to in lens encoder units.
        """
        response = self._send_command('fa{:d}'.format(int(position)), response_length=1)
        if response[0][:4] != 'DONE':
            self.logger.error(
                "{} got response '{}', expected 'DONENNNNN,N'!".format(
                    self, response[0].rstrip()))
        else:
            r = response[0][4:].rstrip()
            self.logger.debug("Moved to {} encoder units".format(r[:-2]))
            if r[-1] == '1':
                self.logger.warning('{} reported hitting a focus stop'.format(self))
            return int(r[:-2])

    def move_by(self, increment):
        """
        Move the focus to a specific position in lens encoder units.
        Does not do any checking of the requested increment but will warn if the lens reports hitting a stop.
        Returns the actual distance moved in lens encoder units.
        """
        response = self._send_command('mf{:d}'.format(increment), response_length=1)
        if response[0][:4] != 'DONE':
            self.logger.error(
                "{} got response '{}', expected 'DONENNNNN,N'!".format(
                    self, response[0].rstrip()))
        else:
            r = response[0][4:].rstrip()
            self.logger.debug("Moved by {} encoder units".format(r[:-2]))
            if r[-1] == '1':
                self.logger.warning('{} reported hitting a focus stop'.format(self))
            return int(r[:-2])

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
            list: possibly empty list containing the '\r' terminated lines of the response from the adaptor.
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
        assert echo == command

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
                    self.logger.error("{} returned error message '{}'!".format(self, error_message))
                except Exception:
                    self.logger.error(
                        "Unknown error '{}' from {}!".format(
                            error_match.group(), self))

        return response

    def _get_serial_number(self):
        response = self._send_command('sn', response_length=1)
        self._serial_number = response[0].rstrip()
        self.logger.debug(
            "Got serial number {} for {} on {}".format(
                self.uid, self.name, self.port))

    def _initialise_aperture(self):
        self.logger.debug('Initialising aperture motor')
        response = self._send_command('in', response_length=1)
        if response[0].rstrip() != 'DONE':
            self.logger.error(
                "{} got response '{}', expected 'DONE'!".format(
                    self, response[0].rstrip()))

    def _move_zero(self):
        response = self._send_command('mz', response_length=1)
        if response[0][:4] != 'DONE':
            self.logger.error(
                "{} got response '{}', expected 'DONENNNNN,1'!".format(
                    self, response[0].rstrip()))
        else:
            r = response[0][4:].rstrip()
            self.logger.debug("Moved {} encoder units to close stop".format(r[:-2]))
            return int(r[:-2])

    def _zero_encoder(self):
        self.logger.debug('Setting focus encoder zero point')
        self._send_command('sf0', response_length=0)

    def _learn_focus_range(self):
        self.logger.debug('Learning absolute focus range')
        response = self._send_command('la', response_length=1)
        if response[0].rstrip() != 'DONE:LA':
            self.logger.error(
                "{} got response '{}', expected 'DONE:LA'!".format(
                    self, response[0].rstrip()))

    def _move_inf(self):
        response = self._send_command('mi', response_length=1)
        if response[0][:4] != 'DONE':
            self.logger.error(
                "{} got response '{}', expected 'DONENNNNN,1'!".format(
                    self, response[0].rstrip()))
        else:
            r = response[0][4:].rstrip()
            self.logger.debug("Moved {} encoder units to far stop".format(r[:-2]))
            return int(r[:-2])


# Error codes should be 'ERR' followed by 1-2 digits
error_pattern = re.compile('(?<=ERR)\d{1,2}')

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
