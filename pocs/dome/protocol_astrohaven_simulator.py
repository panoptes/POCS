import datetime
import queue
from serial import serialutil
import sys
import threading
import time

from pocs.dome import astrohaven
from pocs.tests import serial_handlers
import pocs.utils.logger

Protocol = astrohaven.Protocol
CLOSED_POSITION = 0
NUDGE_OPEN_INCREMENT = 1
NUDGE_CLOSED_INCREMENT = -1
OPEN_POSITION = 10


def _drain_queue(q):
    cmd = None
    while not q.empty():
        cmd = q.get_nowait()
    return cmd  # Present just for debugging.


class Shutter(object):
    """Represents one side of the clamshell dome."""

    def __init__(self, side, open_command, close_command, is_open_char, is_closed_char, logger):
        self.side = side
        self.open_commands = [open_command, Protocol.OPEN_BOTH]
        self.close_commands = [close_command, Protocol.CLOSE_BOTH]
        self.is_open_char = is_open_char
        self.is_closed_char = is_closed_char
        self.logger = logger
        self.position = CLOSED_POSITION
        self.min_position = min(CLOSED_POSITION, OPEN_POSITION)
        self.max_position = max(CLOSED_POSITION, OPEN_POSITION)

    def handle_input(self, input_char):
        ts = datetime.datetime.now()
        msg = ts.strftime('%M:%S.%f')
        if input_char in self.open_commands:
            if self.is_open:
                return (False, self.is_open_char)
            self.logger.info('Opening side %s, starting position %r' % (self.side, self.position))
            self.adjust_position(NUDGE_OPEN_INCREMENT)
            if self.is_open:
                self.logger.info('Opened side %s' % self.side)
                return (True, self.is_open_char)
            return (True, input_char)
        elif input_char in self.close_commands:
            if self.is_closed:
                return (False, self.is_closed_char)
            self.logger.info('Closing side %s, starting position %r' % (self.side, self.position))
            self.adjust_position(NUDGE_CLOSED_INCREMENT)
            if self.is_closed:
                self.logger.info('Closed side %s' % self.side)
                return (True, self.is_closed_char)
            return (True, input_char)
        else:
            return (False, None)

    def adjust_position(self, nudge_by):
        new_position = self.position + nudge_by
        self.position = min(self.max_position, max(self.min_position, new_position))

    @property
    def is_open(self):
        return self.position == OPEN_POSITION

    @property
    def is_closed(self):
        return self.position == CLOSED_POSITION


class AstrohavenPLCSimulator:
    """Simulates the behavior of the Vision 130 PLC in an Astrohaven clamshell dome.

    The RS-232 connection is simulated with an input queue of bytes (one character strings,
    really) and an output queue of bytes (also 1 char strings).

    This class provides a run function which can be called from a Thread to execute.
    """

    def __init__(self, command_queue, status_queue, stop, logger):
        """
        Args:
            command_queue: The queue.Queue instance from which command bytes are read one at a time
                and acted upon.
            status_queue: The queue.Queue instance to which bytes are written one at a time
                (approximately once a second) to report the state of the dome or the response
                to a command byte.
            stop: a threading.Event which is checked to see if run should stop executing.
        """
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.stop = stop
        self.logger = logger
        self.delta = datetime.timedelta(seconds=1)
        self.shutter_a = Shutter('A', Protocol.OPEN_A, Protocol.CLOSE_A, Protocol.A_OPEN_LIMIT,
                                 Protocol.A_CLOSE_LIMIT, self.logger)
        self.shutter_b = Shutter('B', Protocol.OPEN_B, Protocol.CLOSE_B, Protocol.B_OPEN_LIMIT,
                                 Protocol.B_CLOSE_LIMIT, self.logger)
        self.next_output_code = None
        self.next_output_time = None
        self.logger.info('AstrohavenPLCSimulator created')

    def __del__(self):
        if not self.stop.is_set():
            self.logger.critical('AstrohavenPLCSimulator.__del__ stop is NOT set')

    def run(self):
        self.logger.info('AstrohavenPLCSimulator.run ENTER')
        self.next_output_time = datetime.datetime.now()
        while True:
            if self.stop.is_set():
                self.logger.info('Returning from AstrohavenPLCSimulator.run EXIT')
                return
            now = datetime.datetime.now()
            remaining = (self.next_output_time - now).total_seconds()
            self.logger.info('AstrohavenPLCSimulator.run remaining=%r' % remaining)
            if remaining <= 0:
                self.do_output()
                continue
            try:
                c = self.command_queue.get(block=True, timeout=remaining)
            except queue.Empty:
                continue
            if self.handle_input(c):
                # This sleep is here to reflect the fact that responses from the Astrohaven PLC
                # don't appear to be instantaneous, and the Wheaton originated driver had pauses
                # and drains of input from the PLC before accepting a response.
                time.sleep(0.2)
                # Ignore accumulated input (i.e. assume that the PLC is ignore/discarding input
                # while it is performing a command). But do the draining before performing output
                # so that if the driver responds immediately, we don't lose the next command.
                _drain_queue(self.command_queue)
                self.do_output()

    def do_output(self):
        c = self.next_output_code
        if not c:
            c = self.compute_state()
            self.logger.info('AstrohavenPLCSimulator.compute_state -> {!r}', c)
        self.next_output_code = None
        # We drop output if the queue is full.
        if not self.status_queue.full():
            self.status_queue.put(c, block=False)
            self.next_output_time = datetime.datetime.now() + self.delta

    def handle_input(self, c):
        self.logger.info('AstrohavenPLCSimulator.handle_input {!r}', c)
        (a_acted, a_resp) = self.shutter_a.handle_input(c)
        (b_acted, b_resp) = self.shutter_b.handle_input(c)
        # Use a_resp if a_acted or if there is no b_resp
        joint_resp = (a_acted and a_resp) or b_resp or a_resp
        if not (a_acted or b_acted):
            # Might nonetheless be a valid command request. If so, echo the limit response.
            if joint_resp and not self.next_output_code:
                self.next_output_code = joint_resp
                return True
            else:
                return False
        else:
            # Replace the pending output (if any) with the output for this command.
            self.next_output_code = joint_resp
            return True

    def compute_state(self):
        # TODO(jamessynge): Validate that this is correct. In particular, if we start with both
        # shutters closed, then nudge A open a bit, what is reported? Ditto with B only, and with
        # both nudged open (but not fully open).
        if self.shutter_a.is_closed:
            if self.shutter_b.is_closed:
                return Protocol.BOTH_CLOSED
            else:
                return Protocol.B_IS_OPEN
        elif self.shutter_b.is_closed:
            return Protocol.A_IS_OPEN
        else:
            return Protocol.BOTH_OPEN


class AstrohavenSerialSimulator(serial_handlers.NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = pocs.utils.logger.get_root_logger()
        self.plc_thread = None
        self.command_queue = queue.Queue(maxsize=50)
        self.status_queue = queue.Queue(maxsize=1000)
        self.stop = threading.Event()
        self.stop.set()
        self.plc = AstrohavenPLCSimulator(self.command_queue, self.status_queue, self.stop,
                                          self.logger)

    def __del__(self):
        if self.plc_thread:
            self.logger.critical('AstrohavenPLCSimulator.__del__ plc_thread is still present')
            self.stop.set()
            self.plc_thread.join(timeout=3.0)

    def open(self):
        """Open port.

        Raises:
            SerialException if the port cannot be opened.
        """
        if not self.is_open:
            self.is_open = True
            self._reconfigure_port()

    def close(self):
        """Close port immediately."""
        self.is_open = False
        self._reconfigure_port()

    @property
    def in_waiting(self):
        """The number of input bytes available to read immediately."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        return self.status_queue.qsize()

    def reset_input_buffer(self):
        """Flush input buffer, discarding all it’s contents."""
        _drain_queue(self.status_queue)

    def read(self, size=1):
        """Read size bytes.

        If a timeout is set it may return fewer characters than requested.
        With no timeout it will block until the requested number of bytes
        is read.

        Args:
            size: Number of bytes to read.

        Returns:
            Bytes read from the port, of type 'bytes'.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError

        # Not checking if the config is OK, so will try to read from a possibly
        # empty queue if using the wrong baudrate, etc. This is deliberate.

        response = bytearray()
        timeout_obj = serialutil.Timeout(self.timeout)
        while True:
            b = self._read1(timeout_obj)
            if b:
                response += b
                if size is not None and len(response) >= size:
                    break
            else:
                # The timeout expired while in _read1.
                break
            if timeout_obj.expired():
                break
        response = bytes(response)
        self.logger.info('AstrohavenSerialSimulator.read({}) -> {!r}', size, response)
        return response

    @property
    def out_waiting(self):
        """The number of bytes in the output buffer."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        return self.command_queue.qsize()

    def reset_output_buffer(self):
        """Clear output buffer.

        Aborts the current output, discarding all that is in the output buffer.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        _drain_queue(self.command_queue)

    def flush(self):
        """Write the buffered data to the output device.

        We interpret that here as waiting until the PLC simulator has taken all of the
        commands from the queue.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        while not self.command_queue.empty():
            time.sleep(0.01)

    def write(self, data):
        """Write the bytes data to the port.

        Args:
            data: The data to write (bytes or bytearray instance).

        Returns:
            Number of bytes written.

        Raises:
            SerialTimeoutException: In case a write timeout is configured for
                the port and the time is exceeded.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("write takes bytes")
        data = bytes(data)  # Make sure it can't change.
        self.logger.info('AstrohavenSerialSimulator.write({!r})', data)
        count = 0
        timeout_obj = serialutil.Timeout(self.write_timeout)
        for b in data:
            self._write1(b, timeout_obj)
            count += 1
        return count

    # --------------------------------------------------------------------------

    @property
    def is_config_ok(self):
        return (self.baudrate == 9600 and self.bytesize == serialutil.EIGHTBITS and
                self.parity == serialutil.PARITY_NONE and not self.rtscts and not self.dsrdtr)

    def _read1(self, timeout_obj):
        if not self.is_open:
            raise serialutil.portNotOpenError
        try:
            c = self.status_queue.get(block=True, timeout=timeout_obj.time_left())
            assert isinstance(c, str)
            assert len(c) == 1
            b = c.encode(encoding='ascii')
            assert len(c) == 1
            return b
        except queue.Empty:
            return None

    def _write1(self, b, timeout_obj):
        if not self.is_open:
            raise serialutil.portNotOpenError
        try:
            self.command_queue.put(chr(b), block=True, timeout=timeout_obj.time_left())
        except queue.Full:
            # This exception is "lossy" in that the caller can't tell how much was written.
            raise serialutil.writeTimeoutError

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
        need_thread = self.is_open and self.is_config_ok
        if need_thread and not self.plc_thread:
            _drain_queue(self.command_queue)
            _drain_queue(self.status_queue)
            self.stop.clear()
            self.plc_thread = threading.Thread(
                name='Astrohaven PLC Simulator', target=lambda: self.plc.run())
            self.plc_thread.start()
        elif self.plc_thread and not need_thread:
            self.stop.set()
            self.plc_thread.join(timeout=30.0)
            if self.plc_thread.is_alive():
                raise Exception(self.plc_thread.name + " thread did not stop!")
            self.plc_thread = None
            _drain_queue(self.command_queue)
            _drain_queue(self.status_queue)

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


Serial = AstrohavenSerialSimulator
