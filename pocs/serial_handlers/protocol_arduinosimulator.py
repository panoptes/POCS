"""Provides a simple simulator for telemetry_board.ino or camera_board.ino.

We use the pragma "no cover" in several places that happen to never be
reached or that would only be reached if the code was called directly,
i.e. not in the way it is intended to be used.
"""

import copy
import datetime
import json
import queue
import random
from serial import serialutil
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

    def __init__(self, message, relay_queue, json_queue, chunk_size, stop, logger):
        """
        Args:
            message: The message to be sent (millis and report_num will be added).
            relay_queue: The queue.Queue instance from which relay command
                bytes are read and acted upon. Elements are of type bytes.
            json_queue: The queue.Queue instance to which json messages
                (serialized to bytes) are written at ~9600 baud. Elements
                are of type bytes (i.e. each element is a sequence of bytes of
                length up to chunk_size).
            chunk_size: The number of bytes to write to json_queue at a time.
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
        self.chunk_size = chunk_size
        # Interval between outputing chunks of bytes.
        chunks_per_second = 1000.0 / self.chunk_size
        chunk_interval = 1.0 / chunks_per_second
        self.logger.debug('chunks_per_second={}   chunk_interval={}', chunks_per_second,
                          chunk_interval)
        self.chunk_delta = datetime.timedelta(seconds=chunk_interval)
        self.next_chunk_time = None
        self.pending_json_bytes = bytearray()
        self.pending_relay_bytes = bytearray()
        self.command_lines = []
        self.start_time = datetime.datetime.now()
        self.report_num = 0
        self.logger.info('ArduinoSimulator created')

    def __del__(self):
        if not self.stop.is_set():  # pragma: no cover
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
            self.logger.info('Cutting off the leading {} bytes of the first message',
                             cut)
            b = b[cut:]
        self.pending_json_bytes.extend(b)
        # Now two interleaved loops:
        # 1) Generate messages every self.message_delta
        # 2) Emit a chunk of bytes from pending_json_bytes every self.chunk_delta.
        # Clearly we need to emit all the bytes from pending_json_bytes at least
        # as fast as we append new messages to it, else we'll have a problem
        # (i.e. the simulated baud rate will be too slow for the output rate).
        while True:
            if self.stop.is_set():
                self.logger.info('Returning from ArduinoSimulator.run EXIT')
                return
            now = datetime.datetime.now()
            if now >= self.next_chunk_time:
                self.output_next_chunk(now)
            if now >= self.next_message_time:
                self.generate_next_message(now)
            if self.pending_json_bytes and self.next_chunk_time < self.next_message_time:
                next_time = self.next_chunk_time
            else:
                next_time = self.next_message_time
            self.read_relay_queue_until(next_time)

    def handle_pending_relay_bytes(self):
        """Process complete relay commands."""
        newline = b'\n'
        while True:
            index = self.pending_relay_bytes.find(newline)
            if index < 0:
                break
            line = str(self.pending_relay_bytes[0:index], 'ascii')
            self.logger.info(f'Received command: {line}')
            del self.pending_relay_bytes[0:index + 1]
            self.command_lines.append(line)
        if self.pending_relay_bytes:
            self.logger.info(f'Accumulated {len(self.pending_relay_bytes)} bytes.')

    def read_relay_queue_until(self, next_time):
        """Read and process relay queue bytes until time for the next action."""
        while True:
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
                assert isinstance(b, (bytes, bytearray))
                self.pending_relay_bytes.extend(b)
                self.handle_pending_relay_bytes()
                # Fake a baud rate for reading by waiting based on the
                # number of bytes we just read.
                time.sleep(1.0 / 1000 * len(b))
            except queue.Empty:
                # Not returning here so that the return above is will be
                # hit every time this method executes.
                pass

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
        if self.command_lines:
            self.message['commands'] = self.command_lines
            self.command_lines = []

        s = json.dumps(self.message) + '\r\n'
        if 'commands' in self.message:
            del self.message['commands']

        s = s.replace('"Convert to NaN"', 'NaN', 1)
        s = s.replace('"Convert to nan"', 'nan', 1)
        self.logger.debug('generate_next_message -> {!r}', s)
        b = s.encode(encoding='ascii')
        return b


class FakeArduinoSerialHandler(serial_handlers.NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = pocs.utils.logger.get_root_logger()
        self.simulator_thread = None
        self.relay_queue = queue.Queue(maxsize=1)
        self.json_queue = queue.Queue(maxsize=1)
        self.json_bytes = bytearray()
        self.stop = threading.Event()
        self.stop.set()
        self.device_simulator = None

    def __del__(self):
        if self.simulator_thread:  # pragma: no cover
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
            else:  # pragma: no cover
                # The timeout expired while in _read1.
                break
            if timeout_obj.expired():  # pragma: no cover
                break
        response = bytes(response)
        return response

    def readline(self):
        """Read and return one line from the simulator.

        This override exists just to support logging of the line.
        """
        line = super().readline()
        self.logger.debug('FakeArduinoSerialHandler.readline -> {!r}', line)
        return line

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
            raise ValueError('write takes bytes')  # pragma: no cover
        data = bytes(data)  # Make sure it can't change.
        self.logger.info('FakeArduinoSerialHandler.write({!r})', data)
        try:
            for n in range(len(data)):
                one_byte = data[n:n + 1]
                self.relay_queue.put(one_byte, block=True, timeout=self.write_timeout)
            return len(data)
        except queue.Full:  # pragma: no cover
            # This exception is "lossy" in that the caller can't tell how much was written.
            raise serialutil.writeTimeoutError

    # --------------------------------------------------------------------------

    @property
    def is_config_ok(self):
        """Does the caller ask for the correct serial device config?"""
        # The default Arduino data, parity and stop bits are: 8 data bits, no parity, one stop bit.
        v = (self.baudrate == 9600 and self.bytesize == serialutil.EIGHTBITS and
             self.parity == serialutil.PARITY_NONE and not self.rtscts and not self.dsrdtr)

        # All existing tests ensure the config is OK, so we never log here.
        if not v:  # pragma: no cover
            self.logger.critical('Serial config is not OK: {!r}', (self.get_settings(), ))

        return v

    def _read1(self, timeout_obj):
        """Read 1 byte of input, of type bytes."""

        # _read1 is currently called only from read(), which checks that the
        # serial device is open, so is_open is always true.
        if not self.is_open:  # pragma: no cover
            raise serialutil.portNotOpenError

        if not self.json_bytes:
            try:
                entry = self.json_queue.get(block=True, timeout=timeout_obj.time_left())
                assert isinstance(entry, bytes)
                self.json_bytes.extend(entry)
            except queue.Empty:
                return None

        # Unless something has gone wrong, json_bytes is always non-empty here.
        if not self.json_bytes:  # pragma: no cover
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
                name='Device Simulator', target=lambda: self.device_simulator.run(), daemon=True)
            self.simulator_thread.start()
        elif self.simulator_thread and not need_thread:
            self.stop.set()
            self.simulator_thread.join(timeout=30.0)
            if self.simulator_thread.is_alive():
                # Not a SerialException, but a test infrastructure error.
                raise Exception(self.simulator_thread.name + ' thread did not stop!')  # pragma: no cover
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
        # We never set rts in our tests, so this doesn't get executed.
        pass  # pragma: no cover

    def _update_dtr_state(self):
        """Handle dtr being set to some value.

        "self.dtr = value" has been executed, for some value. This may not
        have changed the value.
        """
        # We never set dtr in our tests, so this doesn't get executed.
        pass  # pragma: no cover

    def _update_break_state(self):
        """Handle break_condition being set to some value.

        "self.break_condition = value" has been executed, for some value.
        This may not have changed the value.
        Note that break_condition is set and then cleared by send_break().
        """
        # We never set break_condition in our tests, so this doesn't get executed.
        pass  # pragma: no cover

    # --------------------------------------------------------------------------
    # Internal (non-standard) methods.

    def _params_from_url(self, url):
        """Extract various params from the URL."""
        expected = 'expected a string in the form "arduinosimulator://[?board=<name>]"'
        parts = urllib.parse.urlparse(url)

        # Unless we force things (break the normal protocol), scheme will always
        # be 'arduinosimulator'.
        if parts.scheme != 'arduinosimulator':
            raise Exception(expected + ': got scheme {!r}'.format(parts.scheme))  # pragma: no cover
        int_param_names = {'chunk_size', 'read_buffer_size', 'write_buffer_size'}
        params = {}
        for option, values in urllib.parse.parse_qs(parts.query, True).items():
            if option == 'board' and len(values) == 1:
                params[option] = values[0]
            elif option == 'name' and len(values) == 1:
                # This makes it easier for tests to confirm the right serial device has
                # been opened.
                self.name = values[0]
            elif option in int_param_names and len(values) == 1:
                params[option] = int(values[0])
            else:
                raise Exception(expected + ': unknown param {!r}'.format(option))  # pragma: no cover
        return params

    def _create_simulator(self, params):
        board = params.get('board', 'telemetry')
        if board == 'telemetry':
            message = json.loads("""
                {
                    "name":"telemetry_board",
                    "ver":"2017-09-23",
                    "power": {
                        "computer":1,
                        "fan":1,
                        "mount":1,
                        "cameras":1,
                        "weather":1,
                        "main":1
                    },
                    "current": {"main":387,"fan":28,"mount":34,"cameras":27},
                    "amps": {"main":1083.60,"fan":50.40,"mount":61.20,"cameras":27.00},
                    "humidity":42.60,
                    "temp_00":15.50,
                    "temperature":[13.00,12.81,19.75],
                    "not_a_number":"Convert to nan"
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
                    "humidity":59.60,
                    "temp_00":12.50,
                    "Not_a_Number":"Convert to NaN"
                }
                """)
        elif board == 'json_object':
            # Produce an output that is json, but not what we expect
            message = {}
        else:
            raise Exception('Unknown board: {}'.format(board))  # pragma: no cover

        # The elements of these queues are of type bytes. This means we aren't fully controlling
        # the baudrate unless the chunk_size is 1, but that should be OK.
        chunk_size = params.get('chunk_size', 20)
        self.json_queue = queue.Queue(maxsize=params.get('read_buffer_size', 10000))
        self.relay_queue = queue.Queue(maxsize=params.get('write_buffer_size', 100))

        self.device_simulator = ArduinoSimulator(message, self.relay_queue, self.json_queue,
                                                 chunk_size, self.stop, self.logger)


Serial = FakeArduinoSerialHandler
