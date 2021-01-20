import io
import serial
from warnings import warn
from contextlib import suppress

from panoptes.pocs.focuser import AbstractFocuser


class AbstractSerialFocuser(AbstractFocuser):

    # Class variable to cache the device node scanning results
    _adaptor_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning
    # known focuser devices & acts as a check against adaptors assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self, *args, **kwargs):
        """Initialize an AbstractSerialMount for the port defined in the config.
            Opens a connection to the serial device, if it is valid.
        """

        super().__init__(*args, **kwargs)

        # Check that this node hasn't already been assigned to another focuser device
        if self.port in AbstractSerialFocuser._assigned_nodes:
            message = 'Device node {} already in use!'.format(self.port)
            self.logger.error(message)
            warn(message)
            return

        try:
            self.connect(self.port)
        except (serial.SerialException,
                serial.SerialTimeoutException,
                AssertionError) as err:
            message = 'Error connecting to {} on {}: {}'.format(self.name, self.port, err)
            self.logger.error(message)
            warn(message)
            return

        AbstractSerialFocuser._assigned_nodes.append(self.port)
        self._is_moving = False
        self._initialise()

    def __del__(self):
        with suppress(AttributeError):
            device_node = self.port
            AbstractSerialFocuser._assigned_nodes.remove(device_node)
            self.logger.debug(f'Removed {device_node} from assigned nodes list')
        with suppress(AttributeError):
            self._serial_port.close()
            self.logger.debug(f'Closed serial port {self._port}')

    ##################################################################################################
    # Properties
    ##################################################################################################

    @property
    def is_connected(self):
        """
        Checks status of serial port to determine if connected.
        """
        connected = False
        if self._serial_port:
            connected = self._serial_port.isOpen()
        return connected

    @property
    def is_moving(self):
        """ True if the focuser is currently moving. """
        return self._is_moving

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def _connect(self, port, baudrate):
        try:
            # Configure serial port.
            self._serial_port = serial.Serial()
            self._serial_port.port = port
            self._serial_port.baudrate = baudrate
            self._serial_port.bytesize = serial.EIGHTBITS
            self._serial_port.parity = serial.PARITY_NONE
            self._serial_port.stopbits = serial.STOPBITS_ONE
            self._serial_port.timeout = self.timeout
            self._serial_port.xonxoff = False
            self._serial_port.rtscts = False
            self._serial_port.dsrdtr = False
            self._serial_port.write_timeout = None
            self._inter_byte_timeout = None

            # Establish connection
            self._serial_port.open()

        except serial.SerialException as err:
            self._serial_port = None
            self.logger.critical('Could not open {}!'.format(port))
            raise err

        # Want to use a io.TextWrapper in order to have a readline() method with universal newlines
        # (focuser adaptors usually send '\r', not '\n'). The line_buffering option causes an automatic flush() when
        # a write contains a newline character.
        self._serial_io = io.TextIOWrapper(io.BufferedRWPair(self._serial_port, self._serial_port),
                                           newline='\r', encoding='ascii', line_buffering=True)
        self.logger.debug('Established serial connection to {} on {}.'.format(self.name, port))
