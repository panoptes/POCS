from abc import ABCMeta, abstractmethod, abstractproperty

from .. import PanBase
from ..utils import load_module
from ..utils.logger import get_root_logger

# A dome needs a config. We assume that there is at most one dome in the config,
# i.e. we don't support two different dome devices, such as might be the case
# if there are multiple independent actuators, for example slit, rotation and
# vents.


def CreateDomeFromConfig(config):
    """If there is a dome specified in the config, create a driver for it."""
    logger = get_root_logger()
    if 'dome' not in config:
        logger.debug('No dome in config.')
        return None
    dome_config = config['dome']
    if 'dome' in config.get('simulator', []):
        brand = 'simulator'
        driver = 'simulator'
        dome_config['simulator'] = True
    else:
        brand = dome_config.get('brand')
        driver = dome_config['driver']
    logger.debug('Creating dome: brand={}, driver={}'.format(brand, driver))
    module = load_module('pocs.dome.{}'.format(driver))
    dome = module.Dome(config=config)
    logger.debug('Created dome.')
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
        self._dome_config = self.config['dome']

        # Sub-class directly modifies this property to record changes.
        self._is_connected = False

    @abstractmethod
    def connect(self):  # pragma: no cover
        """Establish a connection to the dome controller.

        The sub-class implementation can access configuration information
        from self._config; see PanBase for more common properties.

        Returns: True if connected, false otherwise.
        """
        return NotImplemented

    @abstractmethod
    def disconnect(self):  # pragma: no cover
        """Disconnect from the dome controller.

        Returns: True if and when disconnected."""
        return NotImplemented

    @abstractmethod
    def open(self):  # pragma: no cover
        """If not known to be open, attempts to open.

        Must already be connected.

        Returns: True if and when open, False if unable to open.
        """
        return NotImplemented

    @abstractmethod
    def close(self):  # pragma: no cover
        """If not known to be closed, attempts to close.

        Must already be connected.

        Returns: True if and when closed, False if unable to close.
        """
        return NotImplemented

    @property
    def is_connected(self):
        """True if connected to the hardware or driver."""
        return self._is_connected

    @abstractproperty
    def is_open(self):  # pragma: no cover
        """True if dome is known to be open."""
        return NotImplemented

    @abstractproperty
    def is_closed(self):  # pragma: no cover
        """True if dome is known to be closed."""
        return NotImplemented

    @abstractproperty
    def state(self):
        """A string representing the state of the dome for presentation.

        Examples: 'Open', 'Closed', 'Opening', 'Closing', 'Left Moving',
        'Right Stuck'

        Returns: A string; the default implementation returns None if the state
          can not be determined from other properties.
        """
        if not self.is_connected():
            return 'Disconnected'
        if self.is_open():
            return 'Open'
        if self.is_closed():
            return 'Closed'
        return None
