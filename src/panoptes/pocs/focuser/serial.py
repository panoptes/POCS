from contextlib import suppress

from panoptes.utils.rs232 import SerialData

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
            self.logger.error(f"Device node {self.port} already in use!")
            return

        try:
            self.connect(self.port)
        except Exception as err:
            self.logger.error(f"Error connecting to {self.name} on {self.port}: {err!r}")
            return

        AbstractSerialFocuser._assigned_nodes.append(self.port)
        self._is_moving = False
        self._initialise()

        # Move to the initial position
        initial_position = kwargs.get("initial_position", None)
        if initial_position is not None:
            self.logger.debug(f"Initial position for {self}: {initial_position}")
            self.move_to(initial_position)

    def __del__(self):
        with suppress(AttributeError):
            device_node = self.port
            AbstractSerialFocuser._assigned_nodes.remove(device_node)
            self.logger.debug(f'Removed {device_node} from assigned nodes list')
        with suppress(AttributeError):
            self._serial.close()
            self.logger.debug(f'Closed serial port {self._port}')

    # Properties

    @property
    def is_connected(self):
        """ Override to use panoptes utils serial code. """
        connected = False
        if self._serial:
            connected = self._serial.is_connected
        return connected

    @property
    def is_moving(self):
        """ True if the focuser is currently moving. """
        return self._is_moving

    # Methods

    def reconnect(self):
        """ Close and open serial port and reconnect to focuser. """
        self.logger.debug(f"Attempting to reconnect to {self}.")
        self.__del__()
        self.connect(port=self.port)

    # Private Methods

    def _connect(self, port, baudrate):
        """ Override the serial device object using panoptes-utils code. """
        self._serial = SerialData(port=port, baudrate=baudrate)
