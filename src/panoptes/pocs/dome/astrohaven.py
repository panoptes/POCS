# Based loosely on the code written by folks at Wheaton College, including:
# https://github.com/goodmanj/domecontrol

import time

from panoptes.pocs.dome import abstract_serial_dome


class Protocol:
    # Status codes, produced when not responding to an input. They are oriented towards
    # reporting whether the two shutters are fully closed.
    BOTH_CLOSED = '0'  # Both A and B shutters are fully closed.

    A_IS_CLOSED = '1'  # Only shutter A is fully closed.
    B_IS_CLOSED = '2'  # Only shutter B is fully closed.

    BOTH_OPEN = '3'  # Really means both NOT fully closed.

    # Status codes produced by the dome when not responding to a movement command.
    STABLE_STATES = (BOTH_CLOSED, BOTH_OPEN, B_IS_CLOSED, A_IS_CLOSED)

    # Limit responses, when the limit has been reached on a direction of movement.
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
    LISTEN_TIMEOUT = 3  # Max number of seconds to wait for a response.
    MOVE_TIMEOUT = 10  # Max number of seconds to run the door motors.
    MOVE_LISTEN_TIMEOUT = 0.1  # When moving, how long to wait for feedback.
    NUM_CLOSE_FEEDBACKS = 2  # Number of target_feedback bytes needed.

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
        v = self._read_state_until_stable()
        if v == Protocol.BOTH_OPEN:
            return True
        self.logger.warning(f'AstrohavenDome.open wrong final state: {v!r}')
        return False

    @property
    def is_closed(self):
        v = self._read_latest_state()
        return v == Protocol.BOTH_CLOSED

    def close(self):
        self._full_move(Protocol.CLOSE_A, Protocol.A_CLOSE_LIMIT,
                        feedback_countdown=AstrohavenDome.NUM_CLOSE_FEEDBACKS)
        self._full_move(Protocol.CLOSE_B, Protocol.B_CLOSE_LIMIT,
                        feedback_countdown=AstrohavenDome.NUM_CLOSE_FEEDBACKS)
        v = self._read_state_until_stable()
        if v == Protocol.BOTH_CLOSED:
            return True
        self.logger.warning(f'AstrohavenDome.close wrong final state: {v!r}')
        return False

    @property
    def status(self):
        """Return a dict with dome's current status."""

        status_lookup = {
            Protocol.BOTH_CLOSED: 'closed_both',
            Protocol.A_IS_CLOSED: 'closed_a',
            Protocol.B_IS_CLOSED: 'closed_b',
            Protocol.BOTH_OPEN: 'open_both',
        }

        state = self._read_latest_state()

        return_status = dict(
            connected=self.is_connected,
        )

        try:
            return_status['open'] = status_lookup[state]
        except KeyError as e:
            return_status['open'] = f'Unexpected response from Astrohaven Dome Controller: {state!r}'

        return return_status

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

    def _read_state_until_stable(self):
        """Read the status until it reaches one of the stable values."""
        end_by = time.time() + AstrohavenDome.LISTEN_TIMEOUT
        c = ''
        while True:
            data = self.serial.read_bytes(size=1)
            if data:
                c = chr(data[-1])
                if c in Protocol.STABLE_STATES:
                    return c
                self.logger.debug(f'_read_state_until_stable not yet stable: data={data!r}')
            if time.time() < end_by:
                continue
            pass
        return c

    def _full_move(self, send, target_feedback, feedback_countdown=1):
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
        # Set a short timeout on reading, so that we don't open or close slowly.
        # In other words, we'll try to read status, but if it isn't available,
        # we'll just send another command.
        saved_timeout = self.serial.ser.timeout
        self.serial.ser.timeout = AstrohavenDome.MOVE_LISTEN_TIMEOUT
        try:
            have_seen_send = False
            end_by = time.time() + AstrohavenDome.MOVE_TIMEOUT
            self.serial.reset_input_buffer()
            # Note that there is no wait in this loop because we have a timeout on reading from
            # the the dome controller, and we know that the dome doesn't echo every character that
            # we send to it.
            while True:
                self.serial.write(send)
                data = self.serial.read_bytes(size=1)
                if data:
                    c = chr(data[-1])
                    if c == target_feedback:
                        feedback_countdown -= 1
                        self.logger.debug(f'Got target_feedback, feedback_countdown={feedback_countdown!r}')
                        if feedback_countdown <= 0:
                            # Woot! Moved the dome and got the desired response.
                            return True
                    elif c == send:
                        have_seen_send = True
                    elif not have_seen_send and c in Protocol.STABLE_STATES:  # pragma: no cover
                        # At the start of looping, we may see the previous stable state until
                        # we start seeing the echo of `send`.
                        pass
                    else:  # pragma: no cover
                        self.logger.warning(f'Unexpected value from dome! send={send!r} target_feedback={target_feedback!r} data={data!r}')
                if time.time() < end_by:
                    continue
                self.logger.error(
                    f'Timed out moving the dome. Check for hardware or communications problem. '
                    f'send={send!r} target_feedback={target_feedback!r} data={data!r}')
                return False
        finally:
            self.serial.ser.timeout = saved_timeout


# Expose as Dome so that we can generically load by module name, without knowing the specific type
# of dome. But for testing, it make sense to *know* that we're dealing with the correct class.
Dome = AstrohavenDome
