"""The protocol_*.py files in this package are based on PySerial's file
test/handlers/protocol_test.py, modified for different behaviors.
The call serial.serial_for_url("XYZ://") looks for a class Serial in a
file named protocol_XYZ.py in this package (i.e. directory).
"""

from serial import serialutil


class NoOpSerial(serialutil.SerialBase):
    """No-op implementation of PySerial's SerialBase.

    Provides no-op implementation of various methods that SerialBase expects
    to have implemented by the sub-class. Can be used as is for a /dev/null
    type of behavior.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

    def reset_input_buffer(self):
        """Remove any accumulated bytes from the device."""
        pass

    def reset_output_buffer(self):
        """Remove any accumulated bytes not yet sent to the device."""
        pass

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
