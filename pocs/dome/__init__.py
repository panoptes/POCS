from abc import ABCMeta, abstractmethod, abstractproperty

import pocs
import pocs.utils
import pocs.utils.logger as logger_module


def create_dome_from_config(config, logger=None):
    """If there is a dome specified in the config, create a driver for it.

    A dome needs a config. We assume that there is at most one dome in the config, i.e. we don't
    support two different dome devices, such as might be the case if there are multiple
    independent actuators, for example slit, rotation and vents. Those would need to be handled
    by a single dome driver class.
    """
    if not logger:
        logger = logger_module.get_root_logger()
    if 'dome' not in config:
        logger.info('No dome in config.')
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
    module = pocs.utils.load_module('pocs.dome.{}'.format(driver))
    dome = module.Dome(config=config)
    logger.info('Created dome driver: brand={}, driver={}'.format(brand, driver))
    return dome


class AbstractDome(pocs.PanBase):
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
        return NotImplemented

    @abstractmethod
    def disconnect(self):  # pragma: no cover
        """Disconnect from the dome controller.

        Raises:
            An exception if unable to disconnect.
        """
        return NotImplemented

    @abstractproperty
    def is_open(self):  # pragma: no cover
        """True if dome is known to be open."""
        return NotImplemented

    @abstractmethod
    def open(self):  # pragma: no cover
        """If not known to be open, attempts to open the dome.

        Must already be connected.

        Returns: True if and when open, False if unable to open.
        """
        return NotImplemented

    @abstractproperty
    def is_closed(self):  # pragma: no cover
        """True if dome is known to be closed."""
        return NotImplemented

    @abstractmethod
    def close(self):  # pragma: no cover
        """If not known to be closed, attempts to close the dome.

        Must already be connected.

        Returns: True if and when closed, False if unable to close.
        """
        return NotImplemented

    @abstractproperty
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
        return NotImplemented
