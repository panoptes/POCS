from abc import ABCMeta, abstractmethod

from panoptes.pocs.base import PanBase
from panoptes.utils.library import load_module
from panoptes.utils.config.client import get_config
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


def create_dome_from_config(config_port='6563', *args, **kwargs):
    """If there is a dome specified in the config, create a driver for it.

    A dome needs a config. We assume that there is at most one dome in the config, i.e. we don't
    support two different dome devices, such as might be the case if there are multiple
    independent actuators, for example slit, rotation and vents. Those would need to be handled
    by a single dome driver class.
    """

    dome_config = get_config('dome', port=config_port)

    if dome_config is None:
        logger.info('No dome in config.')
        return None

    brand = dome_config['brand']
    driver = dome_config['driver']

    logger.debug('Creating dome: brand={}, driver={}'.format(brand, driver))
    module = load_module(f'panoptes.pocs.dome.{driver}')
    dome = module.Dome(config_port=config_port, *args, **kwargs)
    logger.info(f'Created dome driver: brand={brand}, driver={driver}')

    return dome


def create_dome_simulator(config_port=6563, *args, **kwargs):
    dome_config = get_config('dome', port=config_port)

    brand = dome_config['brand']
    driver = dome_config['driver']

    logger.debug('Creating dome simulator: brand={}, driver={}'.format(brand, driver))

    module = load_module(f'panoptes.pocs.dome.{driver}')
    dome = module.Dome(config_port=config_port, *args, **kwargs)
    logger.info('Created dome driver: brand={}, driver={}'.format(brand, driver))

    return dome


class AbstractDome(PanBase):
    """Abstract base class for controlling a non-rotating dome.

    This assumes that the observatory 'dome' is not a classic rotating
    dome with a narrow slit, but instead something like a roll-off roof
    or clam-shell, which can be observed from when open, and that the
    other states (closed or moving) are not used for observing.

    Adding support for a rotating dome would require coordination during
    observing to make sure that the opening tracks the field being observed.
    """
    __metaclass__ = ABCMeta

    def __init__(self, *args, **kwargs):
        """Initialize a PanFixedDome, no connected to the underlying device.

        Customization generally comes from the config file, so that the
        caller doesn't need to know the params needed by a specific type of
        dome interface class.
        """
        super().__init__(*args, **kwargs)
        self._dome_config = self.get_config('dome')

        # Sub-class directly modifies this property to record changes.
        self._is_connected = False

    @property
    def is_connected(self):
        """True if connected to the hardware or driver."""
        return self._is_connected

    @abstractmethod
    def connect(self):  # pragma: no cover
        """Establish a connection to the dome controller.

        The sub-class implementation can access configuration information
        from self._config; see PanBase for more common properties.

        Returns: True if connected, False otherwise.
        """
        return NotImplementedError()

    @abstractmethod
    def disconnect(self):  # pragma: no cover
        """Disconnect from the dome controller.

        Raises:
            An exception if unable to disconnect.
        """
        return NotImplementedError()

    @abstractmethod
    def is_open(self):  # pragma: no cover
        """True if dome is known to be open."""
        return NotImplementedError()

    @abstractmethod
    def open(self):  # pragma: no cover
        """If not known to be open, attempts to open the dome.

        Must already be connected.

        Returns: True if and when open, False if unable to open.
        """
        return NotImplementedError()

    @abstractmethod
    def is_closed(self):  # pragma: no cover
        """True if dome is known to be closed."""
        return NotImplementedError()

    @abstractmethod
    def close(self):  # pragma: no cover
        """If not known to be closed, attempts to close the dome.

        Must already be connected.

        Returns: True if and when closed, False if unable to close.
        """
        return NotImplementedError()

    @property
    @abstractmethod
    def status(self):  # pragma: no cover
        """A string representing the status of the dome for presentation.

        This string is NOT for use in logic, only for presentation, as there is no requirement
        to produce the same string for different types of domes: a roll-off roof might have a
        very different status than a rotating dome that is coordinating its movements with the
        telescope mount.

        Examples: 'Open', 'Closed', 'Opening', 'Closing', 'Left Moving',
        'Right Stuck'

        Returns: A string.
        """
        return NotImplementedError()
