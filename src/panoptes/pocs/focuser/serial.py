import io
import re
import serial
import glob
from warnings import warn
from contextlib import suppress

from panoptes.pocs.focuser import AbstractFocuser


class AbstractSerialFocuser(AbstractFocuser):

    """Serial class of a focuser controller

    Args:
        dev_node_pattern (str, optional): Unix shell pattern to use to identify device nodes that
            may have a Birger adaptor attached. Default is None.
        serial_number_pattern (str, optional): adaptor serial number pattern. Default is None
        baudrate: Rate at which information is transferred in the serial communication channel"""

    # Class variable to cache the device node scanning results
    _adaptor_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning
    # known focuser devices & acts as a check against adaptors assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self, dev_node_pattern=None, serial_number_pattern=None, baudrate=None,
                 *args, **kwargs):
        """Initialize an AbstractSerialMount for the port defined in the config.
            Opens a connection to the serial device, if it is valid.
        """

        self.baudrate = baudrate

        super().__init__(*args, **kwargs)

        self._search_adaptor_node(dev_node_pattern, serial_number_pattern)

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

        if self.initial_position is not None:
            self.position = self.initial_position

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

    def _connect(self, port):
        try:
            # Configure serial port.
            self._serial_port = serial.Serial()
            self._serial_port.port = port
            self._serial_port.baudrate = self.baudrate
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

    def _search_adaptor_node(self, dev_node_pattern, serial_number_pattern):

        if self.name.startwith('Birger'):
            # Birger adaptors serial numbers should be 5 digits
            serial_number_pattern = re.compile(r'^\d{5}$')

        elif self.name.startwith('Astromechanics'):
            # Astromechanics adaptors serial numbers are random alphanumeric combinations
            serial_number_pattern = re.compile(r'^[a-zA-Z0-9_]*$')

        if serial_number_pattern.match(self.port):
            # Have been given a serial number
            self.logger.debug('Looking for {} ({})...'.format(self.name, self.port))

            if AbstractSerialFocuser._adaptor_nodes is None:
                # No cached device nodes scanning results, need to scan.
                self.logger.debug('Getting serial numbers for all connected focusers')
                AbstractSerialFocuser._adaptor_nodes = {}
                # Find nodes matching pattern
                device_nodes = glob.glob(dev_node_pattern)

                # Open each device node and see if a focuser answers
                for device_node in device_nodes:
                    try:
                        serial_number = self.connect(device_node)
                        AbstractSerialFocuser._adaptor_nodes[serial_number] = device_node
                    except (serial.SerialException, serial.SerialTimeoutException, AssertionError):
                        # No focuser on this node.
                        pass
                    finally:
                        self._serial_port.close()

                if not AbstractSerialFocuser._adaptor_nodes:
                    message = 'No focuser devices found!'
                    self.logger.error(message)
                    warn(message)
                    return
                else:
                    self.logger.debug('Connected focusers: {}'.format(AbstractSerialFocuser._adaptor_nodes))

            # Search in cached device node scanning results for serial number
            try:
                device_node = AbstractSerialFocuser._adaptor_nodes[self.port]
            except KeyError:
                message = 'Could not find {} ({})!'.format(self.name, self.port)
                self.logger.error(message)
                warn(message)
                return
            self.logger.debug('Found {} ({}) on {}'.format(self.name, self.port, device_node))
            self.port = device_node
