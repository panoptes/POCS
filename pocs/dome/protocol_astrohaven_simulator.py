print("Importing astrohaven_simulator.py")
print("__name__:", __name__)
print("__file__:", __file__)

import datetime
import queue
from serial import serialutil
import sys
import threading
import time

from pocs.dome import astrohaven
from pocs.tests import serial_handlers


import pytest ### DO NOT COMMIT


Protocol = astrohaven.Protocol

NUDGE_INCREMENT = 0.1


def _drain_queue(q):
    while not q.empty():
        q.get_nowait()


class Shutter(object):
    """Represents one side of the clamshell dome."""

    def __init__(self, side, open_action, close_action, is_open_char, is_closed_char):
        self.side = side
        self.open_actions = [open_action, Protocol.OPEN_BOTH]
        self.close_actions = [close_action, Protocol.CLOSE_BOTH]
        self.is_open_char = is_open_char
        self.is_closed_char = is_closed_char
        self.position = 0.0  # 0 is Closed. 1 is Open.

    def handle_input(self, input_char):
        if input_char in self.open_actions:
            if self.is_open:
                return (False, self.is_open_char)
            self.position = min(1.0, self.position + NUDGE_INCREMENT)
            if self.is_open:
                return (True, self.is_open_char)
            return (True, input_char)
        elif input_char in self.close_actions:
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


class AstrohavenPLCSimulator:
    """Simulates the behavior of the Vision 130 PLC in an Astrohaven clamshell dome.

    The RS-232 connection is simulated with an input queue of bytes (one character strings,
    really) and an output queue of bytes (also 1 char strings).

    This class provides a run function which can be called from a Thread to execute.
    """

    def __init__(self, command_queue, status_queue, stop):
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
        self.delta = datetime.timedelta(seconds=1)
        self.shutter_a = Shutter('A', Protocol.OPEN_A, Protocol.CLOSE_A, Protocol.A_OPEN_LIMIT,
                                 Protocol.A_CLOSE_LIMIT)
        self.shutter_b = Shutter('B', Protocol.OPEN_B, Protocol.CLOSE_B, Protocol.B_OPEN_LIMIT,
                                 Protocol.B_CLOSE_LIMIT)
        self.next_output_code = None
        self.next_output_time = None

    def run(self):
#        pytest.set_trace()
        self.next_output_time = datetime.datetime.now()
        while True:
            if self.stop.is_set():
                print('Returning from AstrohavenPLCSimulator.run', file=sys.stderr)
            now = datetime.datetime.now()
            remaining = (self.next_output_time - now).total_seconds()
            print('AstrohavenPLCSimulator.run remaining=%r' % remaining, file=sys.stderr)
            if remaining <= 0:
                self.do_output()
                self.update_next_output_time()
                continue
            # Maybe a short delay here?
            try:
                c = self.command_queue.get(block=True, timeout=remaining)
            except queue.Empty:
                continue
            if not self.handle_input(c):
                continue
            # We took an action, so let's make that take some time.
            time.sleep(0.25)
            pass

    def do_output(self):
        c = self.next_output_code or self.compute_state()
        self.next_output_code = None
        # We drop output if the queue is full.
        if not self.status_queue.full():
            self.status_queue.put(c, block=False)

    def handle_input(self, c):
        (a_acted, a_resp) = self.shutter_a.handle_input(c)
        (b_acted, b_resp) = self.shutter_b.handle_input(c)
        # Use a_resp if a_acted or if there is no b_resp
        joint_resp = (a_acted and a_resp) or b_resp or a_resp
        if not (a_acted or b_acted):
            # Might nonetheless be a valid action request. If so, echo the limit response.
            if joint_resp and not self.next_output_code:
                self.next_output_code = joint_resp
            return False
        # Ignore accumulated input (i.e. assume it takes a little while to process each
        # character, during which time the PLC may be ignoring or discarding input).
        _drain_queue(self.command_queue)
        # Replace the pending output (if any) with the output for this action.
        self.next_output_code = joint_resp
        return True

    def compute_state(self):
        # TODO(jamessynge): Validate that this is correct. In particular, if we start with both
        # shutters closed, then nudge A open a bit, what is reported. Ditto with B only, and with
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

    def update_next_output_time(self):
        now = datetime.datetime.now()
        self.next_output_time += self.delta
        # Reduce complexities while debugging: if we get behind, so that next_output_time is
        # already in the past, advance it forward.
        if self.next_output_time < now:
            self.next_output_time = now


class AstrohavenSerialSimulator(serial_handlers.NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plc_thread = None
        self.command_queue = queue.Queue(maxsize=4)
        self.status_queue = queue.Queue(maxsize=1000)
        self.stop = threading.Event()
        self.plc = AstrohavenPLCSimulator(self.command_queue, self.status_queue, self.stop)

    def __del__(self):
        if self.plc_thread:
            self.stop.set()
            self.plc_thread.join(timeout=1.0)

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
        return bytes(response)

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
        if not self.is_open:
            raise serialutil.portNotOpenError
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("write takes bytes")
        data = bytes(data)  # Make sure it can't change.
        count = 0
        timeout_obj = serialutil.Timeout(self.write_timeout)
        for b in data:
            self.write1(b, timeout_obj)
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

if __name__ == '__main__':
    sim = AstrohavenPLCSimulator(command_queue=None, status_queue=None, stop=None)
    pass
