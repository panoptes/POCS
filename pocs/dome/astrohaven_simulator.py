print("Importing astrohaven_simulator.py")
print("__name__:", __name__)
print("__file__:", __file__)

import datetime
import queue
import threading

from pocs.dome import astrohaven
from pocs.test import serial_handlers

Protocol = astrohaven.Protocol

NUDGE_INCREMENT = 0.1


class Shutter(object):
    """Represents one side of the clamshell dome."""
    def __init__(self, side, open_action, close_action, is_open_char, is_closed_char):
        self.side = side
        self.open_action = open_action
        self.close_action = close_action
        self.is_open_char = is_open_char
        self.is_closed_char = is_closed_char
        self.position = 0.0  # 0 is Closed. 1 is Open.

    def handle_input(self, input_char):
        if input_char == self.open_action:
            if self.is_open:
                return (False, self.is_open_char)
            self.position = min(1.0, self.position + NUDGE_INCREMENT)
            if self.is_open:
                return (True, self.is_open_char)
            return (True, input_char)
        elif input_char == self.close_action:
            if self.is_closed:
                return (False, self.is_closed_char)
            self.position = max(0.0, self.position - NUDGE_INCREMENT)
            if self.is_closed:
                return (True, self.is_closed_char)
            return (True, input_char)
        else:
            return (False, None)

    @property
    def is_open(self):
        return self.position >= 1.0

    @property
    def is_closed(self):
        return self.position <= 0.0


class AstrohavenPLCSimulator(threading.Thread):
    def __init__(self, input_queue, output_queue, stop, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.stop = stop
        self.delta = datetime.timedelta(seconds=1)
        self.shutter_a = Shutter('A', Protocol.OPEN_A, Protocol.CLOSE_A,
                                 Protocol.A_OPEN_LIMIT, Protocol.A_CLOSE_LIMIT)
        self.shutter_b = Shutter('B', Protocol.OPEN_B, Protocol.CLOSE_B,
                                 Protocol.B_OPEN_LIMIT, Protocol.B_CLOSE_LIMIT)

    def run(self):
        next_output = datetime.datetime.now()
        while not self.stop.is_set():
            now = datetime.datetime.now()
            remaining = now - next_output
            if remaining <= 0:
                self.do_output()
                next_output += self.delta
                remaining = now - next_output
            try:
                c = self.input_queue.get(block=True, timeout=remaining.total_seconds())
                if self.handle_input(c):
                    # We 
            except queue.Empty:
                pass

    def do_output(self):
        pass

    def handle_input(self, c):
        (a_acted, a_resp) = self.shutter_a.handle_input(c)
        (b_acted, b_resp) = self.shutter_b.handle_input(c)
        if a_acted or b_acted:
            # Ignore accumulated input (i.e. assume it takes a little while to process each
            # character, during which time the PLC may be ignoring or discarding input).
            while not self.input_queue.empty():
                self.input_queue.get_nowait()
            return True
        if 
        self.output_queue.put(a_resp or b_resp, block=False)
        return False


class AstrohavenSimulator(serial_handlers.NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Position is 0.0 to 1.0 (Closed to Open)
        self.shutter_a = Shutter('A', Protocol.OPEN_A, Protocol.CLOSE_A,
                                 Protocol.A_OPEN_LIMIT, Protocol.A_CLOSE_LIMIT)
        self.shutter_b = Shutter('B', Protocol.OPEN_B, Protocol.CLOSE_B,
                                 Protocol.B_OPEN_LIMIT, Protocol.B_CLOSE_LIMIT)

    @property
    def in_waiting(self):
        """The number of input bytes available to read immediately."""
        return 0

    def open(self):
        """Open port.

        Raises:
            SerialException if the port cannot be opened.
        """
        self.is_open = True

    def close(self):
        """Close port immediately."""
        self.is_open = False

    def read(self, size=1):
        """Read size bytes.

        If a timeout is set it may return fewer characters than requested.
        With no timeout it will block until the requested number of bytes
        is read.

        Args:
            size: Number of bytes to read.

        Returns:
            Bytes read from the port, of type 'bytes'.

        Raises:
            SerialTimeoutException: In case a write timeout is configured for
                the port and the time is exceeded.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        return bytes()

    def write(self, data):
        """
        Args:
            data: The data to write.

        Returns:
            Number of bytes written.

        Raises:
            SerialTimeoutException: In case a write timeout is configured for
                the port and the time is exceeded.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        return 0

    # --------------------------------------------------------------------------
    def is_config_ok(self):
        if self._config_ok is None:
            self._config_ok = (self.baudrate == 9600 and
            self.bytesize = EIGHTBITS and 
            self.parity = PARITY_NONE and
            self.xonxoff == False)
        return self._config_ok

    # --------------------------------------------------------------------------
    # There are a number of methods called by SerialBase that need to be
    # implemented by sub-classes, assuming their calls haven't been blocked
    # by replacing the calling methods/properties. These are no-op
    # implementations.

    def _reconfigure_port(self):
        """Reconfigure the open port after a property has been changed.

        If you need to know which property has been changed, override the
        setter for the appropriate properties.
        """
        self._config_ok = None
        pass

    def _update_rts_state(self):
        """Handle rts being set to some value.

        "self.rts = value" has been executed, for some value. This may not
        have changed the value.
        """
        pass

    def _update_dtr_state(self):
        """Handle dtr being set to some value.

        "self.dtr = value" has been executed, for some value. This may not
        have changed the value.
        """
        pass

    def _update_break_state(self):
        """Handle break_condition being set to some value.

        "self.break_condition = value" has been executed, for some value.
        This may not have changed the value.
        Note that break_condition is set and then cleared by send_break().
        """
        pass



