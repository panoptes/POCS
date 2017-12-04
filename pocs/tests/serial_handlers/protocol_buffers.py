# This module implements a handler for serial_for_url("buffers://").

from pocs.tests.serial_handlers import NoOpSerial

import io
import threading

# r_buffer and w_buffer are binary I/O buffers. read(size=N) on an instance
# of Serial reads the next N bytes from r_buffer, and write(data) appends the
# bytes of data to w_buffer.
# NOTE: The caller (a test) is responsible for resetting buffers before tests.
_r_buffer = None
_w_buffer = None

# The above I/O buffers are not thread safe, so we need to lock them during
# access.
_r_lock = threading.Lock()
_w_lock = threading.Lock()


def ResetBuffers(read_data=None):
    SetRBufferValue(read_data)
    with _w_lock:
        global _w_buffer
        _w_buffer = io.BytesIO()


def SetRBufferValue(data):
    """Sets the r buffer to data (a bytes object)."""
    if data and not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must by a bytes or bytearray object.")
    with _r_lock:
        global _r_buffer
        _r_buffer = io.BytesIO(data)


def GetWBufferValue():
    """Returns an immutable bytes object with the value of the w buffer."""
    with _w_lock:
        if _w_buffer:
            return _w_buffer.getvalue()


class BuffersSerial(NoOpSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def in_waiting(self):
        if not self.is_open:
            raise serialutil.portNotOpenError
        with _r_lock:
            return len(_r_buffer.getbuffer()) - _r_buffer.tell()

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
        with _r_lock:
            # TODO(jamessynge): Figure out whether and how to handle timeout.
            # We might choose to generate a timeout if the caller asks for data
            # beyond the end of the buffer; or simply return what is left,
            # including nothing (i.e. bytes()) if there is nothing left.
            return _r_buffer.read(size)

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
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must by a bytes or bytearray object.")
        if not self.is_open:
            raise serialutil.portNotOpenError
        with _w_lock:
            return _w_buffer.write(data)


Serial = BuffersSerial
