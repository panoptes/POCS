from pocs.focuser.focuser import AbstractFocuser
import serial
import io
import re

class Focuser(AbstractFocuser):
    """
    Focuser class for control of a Canon DSLR lens via a Birger Engineering Canon EF-232 adapter
    """
    def __init__(self,
                 name='Birger Focuser',
                 model='Canon EF-232',
                 *args, **kwargs):
        super().__init__(*args, name=name, model=model, **kwargs)
        self.logger.debug('Initialising Birger focuser')
        self.connect()

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
    def position(self):
        """
        Returns current focus position in the lens focus encoder units
        """
        return int(self._send_command('pf'))

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

        # Want to use a io.TextWrapper in order to have a readline() method with universal newlines
        # (Birger sends '\r', not '\n'). The line_buffering options causes an automatic flush()
        # of the output buffer when writing a newline, i.e. after each command.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {}.'.format(self))

        # Set 'terse' and 'new' response modes. The response from this depends on
        # what the current mode is. For now just discard it.
        self._send_command('rm0,0', check_response=False)

        # Get serial number. Note, this is the serial number of the Birger adaptor,
        # *not* the attached lens (which would be more useful).
        self._serial_number = self._send_command('sn')

        # Initialise the aperture motor. This also has the side effect of fully opening the iris.
        self.logger.debug('Initialising aperture motor')
        self._send_command('in')

        # Initalise focus. First move the focus to the close stop.
        self.logger.debug('Moving focus to close stop')
        self._send_command('mz')
        # The reset the focus encoder counts to 0
        self.logger.debug('Setting focus encoder zero point')
        self._send_command('sf0')
        # Calibrate the focus with the 'Learn Absolute Focus Range' command
        self.logger.debug('Learning absolute focus range')
        self._send_command('la')

        # Finally move the focus to the far stop.
        self.logger.debug('Moving focus to far stop')
        self._send_command('mi')

        self.logger.info('{} initialised'.format(self))

    def move_to(self, position):
        """
        Move the focus to a specific position in lens encoder units.
        Does not do any checking of the requested position but will warn if the lens reports hitting a stop.
        Returns the actual position moved to in lens encoder units.
        """
        self.logger.debug('Moving {} focus to {}'.format(self, position))
        response = self._send_command('fa{:d}'.format(position)) 
        if response[-1] == '1':
            self.logger.warning('{} reported hitting a focus stop'.format(self))
        return int(response[4:-2])

    def move_by(self, increment):
        """
        """
        self.logger.debug('Moving {} focus by {}'.format(self, increment))
        response = self._send_command('mf{:d}'.format(increment))
        if response[-1] == '1':
            self.logger.warning('{} reporting hitting a focus stop'.format(self))
        return int(response[4:-2])

##################################################################################################
# Private Methods
##################################################################################################

    def _send_command(self, command, check_response=True):
        if not self.is_connected:
            self.logger.critical("Attempt to send command to {} when not connected!".format(self))
            return

        # Clear the input buffer in case there's anything left over in there.
        self._serial_port.reset_input_buffer()

        # Send command
        self._serial_io.write(command + '\r')

        if check_response:
            # Get response
            response = self._serial_io.readline().rstrip()
            # Response will begin with either 0 (success) or some other number
            if response.startswith('0'):
                # All OK, return the rest of the response (if any)
                if len(response) > 1:
                    return response[1:]
            else:
                # Something has gone wrong. Response should start with a 1-2 digit
                # error code. Parse it and return the rest of the response (if any).
                try:
                    error_match = error_pattern.match(response)
                    error_message = error_messages[int(error_match.group())]
                    self.logger.error("{} returned error message '{}'!".format(self, error_message))
                    if len(response) > error_match.end():
                        self.logger.error("In addition {} returned'{}'".format(self, response[error_match.end():]))
                except:
                    self.logger.error("Could not parse response '{}' from {}!".format(response, self))


# Error codes should be 1-2 digits
error_pattern = re.compile('\d{1,2}')
                                       
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
