# This module implements a handler for serial_for_url("no_op://").

import io
from serial.serialutil import SerialBase, SerialException, portNotOpenError


class Serial(SerialBase, io.RawIOBase):
    """Pseudo-Serial class for url test://"""

    def __init__(self, *args, **kwargs):
        self.logger = None
        super().__init__(*args, **kwargs)

    def open(self):
        """Open port.
        
        Raises:
            SerialException if the port cannot be opened.
        """
        self._isOpen = True

    def close(self):
        """Close port"""
        self._isOpen = False

    def read(self, size=1):
        """Read size bytes from the serial port."""
        if not self._isOpen:
            raise portNotOpenError
        return bytes()

    def write(self, data):
        """Write the given data to the serial port."""
        if not self._isOpen:
            raise portNotOpenError
        return len(data)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    @property
    def in_waiting(self):
        """Return the number of characters currently in the input buffer."""
        if not self._isOpen:
            raise portNotOpenError
        return 0  # Nothing waiting.

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

    def setBreak(self, level=True):
        """Set break: Controls TXD. When active, to transmitting is
        possible."""
        if not self._isOpen:
            raise portNotOpenError
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
