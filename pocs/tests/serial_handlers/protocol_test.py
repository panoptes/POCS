# This is based on PySerial's file test/handlers/protocol_test.py (i.e. is
# a copy of it, that I'll then modify for testing).
#
# This module implements a URL dummy handler for serial_for_url.
# Apparently the file name needs to be protocol_<name-of-protocol>,
# where here that is "test", allowing URL's of the format "test://".

from abc import ABCMeta, abstractmethod, abstractproperty
import io
from serial.serialutil import SerialBase, SerialException, portNotOpenError
import time

the_hook_creator = None


class AbstractSerialHooks(object):
    def __init__(self, ser, *args, **kwargs):
        self.ser = ser

    def created(self):
        pass

    def open(self):
        """Open port.
        
        Raises:
            SerialException if the port cannot be opened.
        """
        self.ser._isOpen = True

    def close(self):
        """Close port"""
        self.ser._isOpen = False

    @abstractmethod
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
        return NotImplemented

    @abstractmethod
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
        return NotImplemented


class SimpleSerialHooks(object):
    def __init__(self, ser, read_from_bytes, *args, **kwargs):
        super().__init__(ser, *args, **kwargs)
        self.read_from_bytes = read_from_bytes
        self.write_to_byte_array = bytearray()

    def read(self, size=1):
        if size >= len(self.read_from_bytes):
            result = bytes(self.read_from_bytes)
            self.read_from_bytes = ""
            return result
        else:
            result = bytes(self.read_from_bytes[0:size])
            self.read_from_bytes = del self.read_from_bytes[0:size]
            return result

    def write(self, data):
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        self.write_to_byte_array.extend(data)
        return len(data)


def RegisterHookCreator(fn):
    global the_hook_creator
    the_hook_creator = fn


def ClearHookCreator():
    global the_hook_creator
    the_hook_creator = None


class Serial(SerialBase, io.RawIOBase):
    """Pseudo-Serial class for url test://"""

    def __init__(self, *args, **kwargs):
        # Read-write property values
        self._break_condition = False
        self._rts = False
        self._dtr = False
        # Read-only property values
        self._name = False
        self._rts = False
        self._ctx = False
        self._dsr = False
        self._ri = False
        self._ri = False
        self._ri = False
        self._ri = False
        self.logger = None
        self.hooks = the_hook_creator(self, *args, **kwargs)
        super().__init__(*args, **kwargs)
        self.hooks.created(self)

    def open(self):
        """Open port.
        
        Raises:
            SerialException if the port cannot be opened.
        """
        self.hooks.open()

    def close(self):
        """Close port"""
        self.hooks.close()

    def read(self, size=1):
        """Read size bytes from the serial port."""
        if not self._isOpen:
            raise portNotOpenError
        return self.hooks.read(size)

    def write(self, data):
        """Write the given data to the serial port."""
        if not self._isOpen:
            raise portNotOpenError
        return self.hooks.write(data)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    @property
    def in_waiting(self):
        """Return the number of characters currently in the input buffer."""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            # set this one to debug as the function could be called often...
            self.logger.debug('WARNING: in_waiting returns dummy value')
        return 0  # hmmm, see comment in read()

    def reset_input_buffer(self):
        """Flush input buffer, discarding all it’s contents."""
        if not self._isOpen:
            raise portNotOpenError

    def reset_output_buffer(self):
        """Clear output buffer.
        
        Clear output buffer, aborting the current output and discarding
        all that is in the buffer.
        """
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('ignored flushOutput')

    def send_break(self, duration=0.25):
        """Send break condition. Timed, returns to idle state after given
        duration."""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('ignored sendBreak({!r})'.format(duration))

    @property
    def break_condition(self):
        """Get break_condition."""
        return self.__break_condition

    @break_condition.setter
    def break_condition(self, value):
        """Set break_condition: Controls TXD. When active, to transmitting is
        possible."""
        self.__break_condition = value
        if self.logger:
            self.logger.info('ignored setBreak({!r})'.format(level))

    def setRTS(self, level=True):
        """Set terminal status line: Request To Send"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('ignored setRTS({!r})'.format(level))

    def setDTR(self, level=True):
        """Set terminal status line: Data Terminal Ready"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('ignored setDTR({!r})'.format(level))

    def getCTS(self):
        """Read terminal status line: Clear To Send"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('returning dummy for getCTS()')
        return True

    def getDSR(self):
        """Read terminal status line: Data Set Ready"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('returning dummy for getDSR()')
        return True

    def getRI(self):
        """Read terminal status line: Ring Indicator"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('returning dummy for getRI()')
        return False

    def getCD(self):
        """Read terminal status line: Carrier Detect"""
        if not self._isOpen:
            raise portNotOpenError
        if self.logger:
            self.logger.info('returning dummy for getCD()')
        return True
