from abc import abstractmethod
from contextlib import suppress

from panoptes.utils.rs232 import SerialData

from panoptes.pocs.focuser import AbstractFocuser


class AbstractSerialFocuser(AbstractFocuser):
    # Class variable to cache the device node scanning results
    _adaptor_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning
    # known focuser devices & acts as a check against adaptors assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self, baudrate=None, initial_position=None, *args, **kwargs):
        """
        Args:
            initial_position (int, optional): If provided, move to this position after
                initializing.
            baudrate (int, optional): The baudrate of the serial device. Default: None.
            **kwargs: Parsed to AbstractFocuser init function.
        """
        super().__init__(*args, **kwargs)

        self.baudrate = baudrate
        self._is_moving = False

        # Check that this node hasn't already been assigned to another focuser device
        if self.port in AbstractSerialFocuser._assigned_nodes:
            self.logger.error(f"Device node {self.port} already in use!")
            return

        # Connect to the serial device
        try:
            self.connect(port=self.port, baudrate=self.baudrate)
        except Exception as err:
            self.logger.error(f"Error connecting to {self.name} on {self.port}: {err!r}")
            return

        # Initialize the focuser
        self._initialize()
        AbstractSerialFocuser._assigned_nodes.append(self.port)
        self.logger.info(f'Successfully initialized {self}.')

        # Move to the initial position
        # TODO: Move this to Focuser base class?
        if initial_position is not None:
            self.logger.info(f"Initial position for {self}: {initial_position}")
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
        """ True if the focuser serial device is currently connected. """
        if self._serial:
            return self._serial.is_connected
        return False

    @property
    def is_moving(self):
        """ True if the focuser is currently moving. """
        return self._is_moving

    # Methods

    def connect(self, *args, **kwargs):
        """ Connect to the serial device.
        Args:
            *args, **kwargs: Parsed to SerialData.
        """
        self._serial = SerialData(*args, **kwargs)

    def reconnect(self):
        """ Close and open serial port and reconnect to focuser. """
        self.logger.debug(f"Attempting to reconnect to {self}.")
        self.__del__()
        self.connect(port=self.port)

    # Private Methods

    @abstractmethod
    def _initialize(self):
        """ Device - specific initialization. """
        raise NotImplementedError
