"""Provides a simple simulator for telemetry_board.ino or camera_board.ino."""

import copy
import datetime
import json
import queue
import random
from serial import serialutil
import sys
import threading
import time
import urllib

from pocs.tests import serial_handlers
import pocs.utils.logger


def _drain_queue(q):
    cmd = None
    while not q.empty():
        cmd = q.get_nowait()
    return cmd  # Present just for debugging.


class ArduinoSimulator:
    """Simulates the serial behavior of the PANOPTES Arduino sketches.

    The RS-232 connection is simulated with an input and output queue of bytes. This class provides
    a run function which can be called from a Thread to execute. Every two seconds while running it
    will generate another json output line, and then send that to the json_queue in small chunks
    at a rate similar to 9600 baud, the rate used by our Arduino sketches.
    """

    def __init__(self, message, relay_queue, json_queue, stop, logger):
        """
        Args:
            message: The message to be sent (millis and report_num will be added).
            relay_queue: The queue.Queue instance from which replay command bytes are read
                and acted upon. Elements are of type bytes.
            json_queue: The queue.Queue instance to which json messages (serialized to bytes)
                are written at ~9600 baud. Elements are of type bytes.
            stop: a threading.Event which is checked to see if run should stop executing.
            logger: the Python logger to use for reporting messages.
        """
        self.message = copy.deepcopy(message)
        self.relay_queue = relay_queue
        self.json_queue = json_queue
        self.stop = stop
        self.logger = logger
        # Time between producing messages.
        self.message_delta = datetime.timedelta(seconds=2)
        self.next_message_time = None
        # Size of a chunk of bytes.
        self.chunk_size = 20
        # Interval between outputing chunks of bytes.
        chunks_per_second = 1000.0 / self.chunk_size
        chunk_interval = 1.0 / chunks_per_second
        self.logger.debug('chunks_per_second={}   chunk_interval={}',
                          chunks_per_second, chunk_interval)
        self.chunk_delta = datetime.timedelta(seconds=chunk_interval)
        self.next_chunk_time = None
        self.pending_json_bytes = bytearray()
        self.pending_relay_bytes = bytearray()
        self.start_time = datetime.datetime.now()
        self.report_num = 0
        self.logger.info('ArduinoSimulator created')

    def __del__(self):
        if not self.stop.is_set():
            self.logger.critical('ArduinoSimulator.__del__ stop is NOT set')

    def run(self):
        """Produce messages periodically and emit their bytes at a limited rate."""
        self.logger.info('ArduinoSimulator.run ENTER')
        # Produce a message right away, but remove a random number of bytes at the start to reflect
        # what happens when we connect at a random time to the Arduino.
        now = datetime.datetime.now()
        self.next_chunk_time = now
        self.next_message_time = now + self.message_delta
        b = self.generate_next_message_bytes(now)
        cut = random.randrange(len(b))
        if cut > 0:
            b = b[cut:]
        self.pending_json_bytes.extend(b)
        # Now two interleaved loops:
        # 1) Generate messages every self.message_delta
        # 2) Emit a chunk of bytes from pending_json_bytes every self.chunk_delta.
        while True:
            if self.stop.is_set():
                self.logger.info('Returning from ArduinoSimulator.run EXIT')
                return
            now = datetime.datetime.now()
            if now >= self.next_chunk_time:
                self.output_next_chunk(now)
            if now >= self.next_message_time:
                self.generate_next_message(now)
            self.read_and_handle_relay_queue()
            if self.pending_json_bytes and self.next_chunk_time < self.next_message_time:
                next_time = self.next_chunk_time
            else:
                next_time = self.next_message_time
            self.read_relay_queue_until(next_time)

    def read_and_handle_relay_queue(self):
        """Read all available entries in the relay queue, then handle any complete commands."""
        while not self.relay_queue.empty():
            b = self.relay_queue.get_nowait()
            assert isinstance(b, (bytes, bytearray))
            self.pending_relay_bytes.extend(b)
        self.handle_pending_relay_bytes()

    def handle_pending_relay_bytes(self):
        """Process complete relay commands. NOT YET IMPLEMENTED."""
        if len(self.pending_relay_bytes):
            self.logger.error('ArduinoSimulator.handle_pending_relay_bytes NOT YET IMPLEMENTED')
            self.logger.error('Dropping bytes: {!r}', self.pending_relay_bytes)
            self.pending_relay_bytes.clear()
        pass

    def read_relay_queue_until(self, next_time):
        """Wait for a little bit for relay input, not more than the time until the next action."""
        now = datetime.datetime.now()
        if now >= next_time:
            # Already reached the time for the next main loop event,
            # so return to repeat the main loop.
            return
        remaining = (next_time - now).total_seconds()
        assert remaining > 0
        self.logger.info('ArduinoSimulator.read_relay_queue_until remaining={}', remaining)
        try:
            b = self.relay_queue.get(block=True, timeout=remaining)
        except queue.Empty:
            return
        if b:
            assert isinstance(b, (bytes, bytearray))
            self.pending_relay_bytes.extend(b)
            self.handle_pending_relay_bytes()

    def output_next_chunk(self, now):
        """Output one chunk of pending json bytes."""
        self.next_chunk_time = now + self.chunk_delta
        if len(self.pending_json_bytes) == 0:
            return
        last = min(self.chunk_size, len(self.pending_json_bytes))
        chunk = bytes(self.pending_json_bytes[0:last])
        del self.pending_json_bytes[0:last]
        if self.json_queue.full():
            self.logger.info('Dropping chunk because the queue is full')
            return
        self.json_queue.put_nowait(chunk)
        self.logger.debug('output_next_chunk -> {}', chunk)

    def generate_next_message(self, now):
        """Append the next message to the pending bytearray and scheduled the next message."""
        b = self.generate_next_message_bytes(now)
        self.pending_json_bytes.extend(b)
        self.next_message_time = datetime.datetime.now() + self.message_delta

    def generate_next_message_bytes(self, now):
        """Generate the next message (report) from the simulated Arduino."""
        # Not worrying here about emulating the 32-bit nature of millis (wraps in 49 days)
        elapsed = int((now - self.start_time).total_seconds() * 1000)
        self.report_num += 1
        self.message['millis'] = elapsed
        self.message['report_num'] = self.report_num
        s = json.dumps(self.message) + '\r\n'
        self.logger.debug('generate_next_message -> {!r}', s)
        b = s.encode(encoding='ascii')
        return b


class FakeArduinoSerialHandler(serial_handlers.NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = pocs.utils.logger.get_root_logger()
        self.simulator_thread = None
        # The elements of these queues are of type bytes. This means we aren't fully controlling
        # the baudrate, but that should be OK.
        self.relay_queue = queue.Queue(maxsize=100)
        self.json_queue = queue.Queue(maxsize=10000)
        self.json_bytes = bytearray()
        self.stop = threading.Event()
        self.stop.set()
        self.device_simulator = None

    def __del__(self):
        if self.simulator_thread:
            self.logger.critical('ArduinoSimulator.__del__ simulator_thread is still present')
            self.stop.set()
            self.simulator_thread.join(timeout=3.0)

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
        # Not an accurate count because the elements of self.json_queue are arrays, not individual
        # bytes.
        return len(self.json_bytes) + self.json_queue.qsize()

    def reset_input_buffer(self):
        """Flush input buffer, discarding all it’s contents."""
        self.json_bytes.clear()
        _drain_queue(self.json_queue)

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
                response.extend(b)
                if size is not None and len(response) >= size:
                    break
            else:
                # The timeout expired while in _read1.
                break
            if timeout_obj.expired():
                break
        response = bytes(response)
        self.logger.info('FakeArduinoSerialHandler.read({}) -> {!r}', size, response)
        return response

    @property
    def out_waiting(self):
        """The number of bytes in the output buffer."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        # Not an accurate count because the elements of self.relay_queue are arrays, not individual
        # bytes.
        return self.relay_queue.qsize()

    def reset_output_buffer(self):
        """Clear output buffer.

        Aborts the current output, discarding all that is in the output buffer.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        _drain_queue(self.relay_queue)

    def flush(self):
        """Write the buffered data to the output device.

        We interpret that here as waiting until the simulator has taken all of the
        entries from the queue.
        """
        if not self.is_open:
            raise serialutil.portNotOpenError
        while not self.relay_queue.empty():
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
        self.logger.info('FakeArduinoSerialHandler.write({!r})', data)
        count = len(data)
        try:
            self.relay_queue.put(data, block=True, timeout=self.write_timeout)
            return len(data)
        except queue.Full:
            # This exception is "lossy" in that the caller can't tell how much was written.
            raise serialutil.writeTimeoutError

    # --------------------------------------------------------------------------

    @property
    def is_config_ok(self):
        """Does the caller ask for the correct serial device config?"""
        # The default Arduino data, parity and stop bits are: 8 data bits, no parity, one stop bit.
        v = (self.baudrate == 9600 and self.bytesize == serialutil.EIGHTBITS and
             self.parity == serialutil.PARITY_NONE and not self.rtscts and not self.dsrdtr)
        if not v:
            self.logger.critical('Serial config is not OK: {!r}', (self.get_settings(),))
        return v

    def _read1(self, timeout_obj):
        """Read 1 byte of input, of type bytes."""
        if not self.is_open:
            raise serialutil.portNotOpenError
        if not self.json_bytes:
            try:
                entry = self.json_queue.get(block=True, timeout=timeout_obj.time_left())
                assert isinstance(entry, bytes)
                self.json_bytes.extend(entry)
            except queue.Empty:
                return None
        if not self.json_bytes:
            return None
        c = bytes(self.json_bytes[0:1])
        del self.json_bytes[0:1]
        return c

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
        if need_thread and not self.simulator_thread:
            _drain_queue(self.relay_queue)
            _drain_queue(self.json_queue)
            self.json_bytes.clear()
            self.stop.clear()
            params = self._params_from_url(self.portstr)
            self._create_simulator(params)
            self.simulator_thread = threading.Thread(
                name='Device Simulator', target=lambda: self.device_simulator.run())
            self.simulator_thread.start()
        elif self.simulator_thread and not need_thread:
            self.stop.set()
            self.simulator_thread.join(timeout=30.0)
            if self.simulator_thread.is_alive():
                # Not a SerialException, but a test infrastructure error.
                raise Exception(self.simulator_thread.name + " thread did not stop!")
            self.simulator_thread = None
            self.device_simulator = None
            _drain_queue(self.relay_queue)
            _drain_queue(self.json_queue)
            self.json_bytes.clear()

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

    # --------------------------------------------------------------------------
    # Internal (non-standard) methods.

    def _params_from_url(self, url):
        """\
        extract host and port from an URL string, other settings are extracted
        an stored in instance
        """
        expected = 'expected a string in the form "arduinosimulator://[?board=<name>]"'
        parts = urllib.parse.urlparse(url)
        if parts.scheme != "arduinosimulator":
            raise Exception(
                expected + ': got scheme {!r}'.format(parts.scheme))
        params = {}
        for option, values in urllib.parse.parse_qs(parts.query, True).items():
            if option == 'board' and len(values) == 1:
                params[option] = values[0]
            elif option == 'name' and len(values) == 1:
                # This makes it easier for tests to confirm the right serial device has
                # been opened.
                self.name = values[0]
            else:
                raise Exception(
                    expected + ': unknown param {!r}'.format(option))
        return params

    def _create_simulator(self, params):
        board = params.get('board', 'telemetry')
        if board == 'telemetry':
            message = json.loads("""
                {
                    "name":"telemetry_board",
                    "ver":"2017-09-23",
                    "power": {"computer":1, "fan":1, "mount":1, "cameras":1, "weather":1, "main":1},
                    "current": {"main":387,"fan":28,"mount":34,"cameras":27},
                    "amps": {"main":1083.60,"fan":50.40,"mount":61.20,"cameras":27.00},
                    "humidity":42.60,
                    "temp_00":15.50,
                    "temperature":[13.00,12.81,19.75]
                }
                """)
        elif board == 'camera':
            message = json.loads("""
                {
                    "name":"camera_board",
                    "inputs":6,
                    "camera_00":1,
                    "camera_01":1,
                    "accelerometer": {"x":-7.02, "y":6.95, "z":1.70, "o": 6},
                    "humidity":59.60, "temp_00":12.50
                }
                """)
        else:
            raise Exception('Unknown board: {}'.format(board))
        self.device_simulator = ArduinoSimulator(
            message, self.relay_queue, self.json_queue, self.stop, self.logger)


Serial = FakeArduinoSerialHandler
