# Based loosely on the code written by folks at Wheaton College, including:
# https://github.com/goodmanj/domecontrol

import time

from pocs.dome import abstract_serial_dome


class Protocol:
    # Response codes
    BOTH_CLOSED = '0'
    BOTH_OPEN = '3'

    # TODO(jamessynge): Confirm and clarify meaning of '1' and '2'
    B_IS_OPEN = '1'
    A_IS_OPEN = '2'

    A_OPEN_LIMIT = 'x'  # Response to asking for A to open, and being at open limit
    A_CLOSE_LIMIT = 'X'  # Response to asking for A to close, and being at close limit

    B_OPEN_LIMIT = 'y'  # Response to asking for B to open, and being at open limit
    B_CLOSE_LIMIT = 'Y'  # Response to asking for B to close, and being at close limit

    # Command codes, echoed while happening
    CLOSE_A = 'A'
    OPEN_A = 'a'

    CLOSE_B = 'B'
    OPEN_B = 'b'

    # These codes are documented for an 18' dome, but appear not to work with the 7' domes
    # we have access to.
    OPEN_BOTH = 'O'
    CLOSE_BOTH = 'C'
    RESET = 'R'


class AstrohavenDome(abstract_serial_dome.AbstractSerialDome):
    """Interface to an Astrohaven clamshell dome with a Vision 130 PLC and RS-232 interface.

    Experience shows that it emits a status byte about once a second, with the codes
    as described in the Protocol class.
    """
    # TODO(jamessynge): Get these from the config file (i.e. per instance), with these values
    # as defaults, though LISTEN_TIMEOUT can just be the timeout config for SerialData.
    LISTEN_TIMEOUT = 3  # Max number of seconds to wait for a response
    MOVE_TIMEOUT = 10  # Max number of seconds to run the door motors

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO(jamessynge): Consider whether to expose settings of the pyserial object thru
        # rs232.SerialData. Probably should. Could use newer dictionary get/set mechanism so
        # that change to SerialData is minimal. Alternately, provide a means of reading
        # that info from the config file in AbstractSerialDome.__init__ and using it to
        # initialize the SerialData instance.

        # Let's use a timeout that is long enough so that we are "guaranteed" a byte of output
        # from the device. 1 second seems too small given that it appears that is the pace of
        # output from the PLC.
        # TODO(jamessynge): Remove this, replace with a value in the config file.
        self.serial.ser.timeout = AstrohavenDome.LISTEN_TIMEOUT

    @property
    def is_open(self):
        v = self._read_latest_state()
        return v == Protocol.BOTH_OPEN

    def open(self):
        self._full_move(Protocol.OPEN_A, Protocol.A_OPEN_LIMIT)
        self._full_move(Protocol.OPEN_B, Protocol.B_OPEN_LIMIT)
        return self.is_open

    @property
    def is_closed(self):
        v = self._read_latest_state()
        return v == Protocol.BOTH_CLOSED

    def close(self):
        self._full_move(Protocol.CLOSE_A, Protocol.A_CLOSE_LIMIT)
        self._full_move(Protocol.CLOSE_B, Protocol.B_CLOSE_LIMIT)
        return self.is_closed

    @property
    def status(self):
        """Return a text string describing dome's current status."""
        if not self.is_connected:
            return 'Not connected to the dome'
        v = self._read_latest_state()
        if v == Protocol.BOTH_CLOSED:
            return 'Both sides closed'
        if v == Protocol.B_IS_OPEN:
            return 'Side B open, side A closed'
        if v == Protocol.A_IS_OPEN:
            return 'Side A open, side B closed'
        if v == Protocol.BOTH_OPEN:
            return 'Both sides open'
        return 'Unexpected response from Astrohaven Dome Controller: %r' % v

    def __str__(self):
        if self.is_connected:
            return self.status
        return 'Disconnected'

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def _read_latest_state(self):
        """Read and return the latest output from the Astrohaven dome controller."""
        # TODO(jamessynge): Add the ability to do a non-blocking read of the available input
        # from self.serial. If there is some input, return it, but don't wait for more. The last
        # received byte is good enough for our purposes... as long as we drained the input buffer
        # before sending a command to the dome.
        self.serial.reset_input_buffer()
        data = self.serial.read_bytes(size=1)
        if len(data):
            return chr(data[-1])
        return None

    def _nudge_shutter(self, send, target_feedback):
        """Send one command to the dome, return whether the desired feedback was received.

        Args:
            send: The command code to send; this is a string of one ASCII character. See
                Protocol above for the command codes.
            target_feedback: The response code to compare to the response from the dome;
                this is a string of one ASCII character. See Protocol above for the codes;
                while the dome is moving, it echoes the command code sent.

        Returns:
            True if the output from the dome is target_feedback; False otherwise.
        """
        self.serial.write(send)
        # Wait a moment so that the response to our command has time to be emitted, and we don't
        # get fooled by a status code received at about the same time that our command is sent.
        time.sleep(0.1)
        feedback = self._read_latest_state()
        return feedback == target_feedback

    def _full_move(self, send, target_feedback):
        """Send a command code until the target_feedback is recieved, or a timeout is reached.

        Args:
            send: The command code to send; this is a string of one ASCII character. See
                Protocol above for the command codes.
            target_feedback: The response code to compare to the response from the dome;
                this is a string of one ASCII character. See Protocol above for the codes;
                while the dome is moving, it echoes the command code sent.
        Returns:
            True if the target_feedback is received from the dome before the MOVE_TIMEOUT;
            False otherwise.
        """
        end_by = time.time() + AstrohavenDome.MOVE_TIMEOUT
        while not self._nudge_shutter(send, target_feedback):
            if time.time() < end_by:
                continue
            self.logger.error('Timed out moving the dome. Check for hardware or communications ' +
                              'problem. send=%r latest_state=%r', send, self._read_latest_state())
            return False
        return True


# Expose as Dome so that we can generically load by module name, without knowing the specific type
# of dome. But for testing, it make sense to *know* that we're dealing with the correct class.
Dome = AstrohavenDome
